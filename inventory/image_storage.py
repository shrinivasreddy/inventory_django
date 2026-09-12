import io
import os
import shutil
import hashlib
from pathlib import Path

from django.conf import settings
from PIL import Image, UnidentifiedImageError


SECTION_IMAGE_FOLDERS = {
    "sign": "sign_inventory",
    "pavement": "pavement_inventory",
    "lane": "lane_inventory",
    "curb": "curb_inventory",
}
FOLDER_SECTIONS = {folder: section for section, folder in SECTION_IMAGE_FOLDERS.items()}
IMAGE_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


class InventoryImageError(ValueError):
    pass


def record_image_directory(section, record_id):
    folder = SECTION_IMAGE_FOLDERS[section]
    return Path(settings.INVENTORY_UPLOAD_ROOT) / "images" / folder / str(record_id)


def simulation_image_directory(project, record_id, slot):
    name = project.name
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip(" .")[:100]
    reserved = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}
    if not safe or safe.upper() in reserved or safe != name or type(project).objects.filter(name__iexact=name).exclude(pk=project.pk).exists():
        safe = (safe or "project") + "-" + str(project.pk) + "-" + hashlib.sha256(name.encode()).hexdigest()[:8]
    category = "night-simulation" if slot == "night_simulation" else "day-simulation"
    return Path(settings.INVENTORY_UPLOAD_ROOT) / category / safe / str(record_id)


def stored_image_path(data, slot):
    storage = data.get("_IMAGE_STORAGE", {})
    if not isinstance(storage, dict):
        return None
    relative = storage.get(slot)
    if not isinstance(relative, str):
        return None
    root = Path(settings.INVENTORY_UPLOAD_ROOT).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root or path.suffix.lower() not in {".jpg", ".png", ".webp"}:
        return None
    return path


def _normalized_image(upload):
    if upload.size > settings.MAX_INVENTORY_IMAGE_BYTES:
        max_mb = settings.MAX_INVENTORY_IMAGE_BYTES // (1024 * 1024)
        raise InventoryImageError(f"Image must be {max_mb} MB or smaller.")
    raw = upload.read()
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(raw)) as source:
            image_format = (source.format or "").upper()
            if image_format not in IMAGE_FORMATS:
                raise InventoryImageError("Upload a JPEG, PNG, or WebP image.")
            if source.width * source.height > settings.MAX_INVENTORY_IMAGE_PIXELS:
                raise InventoryImageError("Image dimensions are too large.")
            source.load()
            extension, content_type = IMAGE_FORMATS[image_format]
            image = source.copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise InventoryImageError("The uploaded file is not a valid image.")

    if image_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    output = io.BytesIO()
    save_options = {"quality": 90, "optimize": True} if image_format == "JPEG" else {}
    image.save(output, format=image_format, **save_options)
    return output.getvalue(), extension, content_type


def save_record_image(section, record_id, upload, slot="image", project=None):
    if slot not in {"image", "night_simulation"}:
        raise InventoryImageError("Unknown image type.")
    content, extension, content_type = _normalized_image(upload)
    directory = (simulation_image_directory(project, record_id, slot)
                 if section == "sign" and project is not None
                 else record_image_directory(section, record_id))
    directory.mkdir(parents=True, exist_ok=True)
    final_path = directory / f"{slot}.{extension}"
    temporary_path = directory / f".{slot}-upload.tmp"
    try:
        with temporary_path.open("wb") as stream:
            stream.write(content)
        os.replace(temporary_path, final_path)
        for existing in directory.iterdir():
            if existing.is_file() and existing.stem == slot and existing != final_path:
                existing.unlink(missing_ok=True)
    finally:
        temporary_path.unlink(missing_ok=True)
    return final_path.name, content_type


def delete_record_image_directory(section, record_id, data=None):
    for slot in ("image", "night_simulation"):
        path = stored_image_path(data or {}, slot)
        if path is not None and path.is_file():
            path.unlink()
            try:
                path.parent.rmdir()
            except OSError:
                pass
    if section not in SECTION_IMAGE_FOLDERS:
        return
    directory = record_image_directory(section, record_id)
    if directory.exists():
        shutil.rmtree(directory)
