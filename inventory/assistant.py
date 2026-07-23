"""Server-side OpenAI integration for prompt-to-inventory previews."""

import json
import os
import uuid
import urllib.error
import urllib.request

from django.conf import settings

from .specs import TAB_ORDER, get_spec


class AssistantError(Exception):
    pass


def transcribe_audio(audio_bytes, filename, content_type):
    if not settings.OPENAI_API_KEY:
        raise AssistantError(
            "Voice transcription is not configured. Set OPENAI_API_KEY in the server .env file."
        )
    boundary = f"----InventoryAssistant{uuid.uuid4().hex}"
    safe_filename = os.path.basename(filename or "inventory-voice.webm")
    safe_filename = safe_filename.replace('"', "").replace("\r", "").replace("\n", "")
    fields = [
        (
            "model",
            settings.OPENAI_TRANSCRIPTION_MODEL.encode("utf-8"),
            None,
            None,
        ),
        (
            "file",
            audio_bytes,
            safe_filename or "inventory-voice.webm",
            content_type or "audio/webm",
        ),
    ]
    body = bytearray()
    for name, value, part_filename, part_type in fields:
        body.extend(f"--{boundary}\r\n".encode())
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if part_filename:
            disposition += f'; filename="{part_filename}"'
        body.extend(f"{disposition}\r\n".encode())
        if part_type:
            body.extend(f"Content-Type: {part_type}\r\n".encode())
        body.extend(b"\r\n")
        body.extend(value)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=settings.OPENAI_ASSISTANT_TIMEOUT,
        ) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AssistantError("The voice transcription request was rejected.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AssistantError("Voice transcription is temporarily unavailable.") from exc
    text = str(parsed.get("text") or "").strip()
    if not text:
        raise AssistantError("No speech was detected in the recording.")
    return text


def _extract_output_text(response):
    parts = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    if not parts:
        raise AssistantError("The assistant returned an empty response.")
    return "".join(parts)


def interpret_inventory_prompt(prompt, safety_identifier):
    if not settings.OPENAI_API_KEY:
        raise AssistantError(
            "The assistant is not configured. Set OPENAI_API_KEY in the server .env file."
        )

    section_fields = {
        key: [column for column in get_spec(key)["columns"] if column != "ID"]
        for key in TAB_ORDER
    }
    schema = {
        "type": "object",
        "properties": {
            "section": {"type": "string", "enum": TAB_ORDER},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["name", "value"],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string"},
        },
        "required": ["section", "fields", "summary"],
        "additionalProperties": False,
    }
    instructions = (
        "Convert the user's instruction into one inventory record preview. "
        "Never invent a value that the user did not provide or clearly imply. "
        "Choose exactly one section. Use field names exactly as listed. "
        "Omit fields with no supplied value. Do not perform any action. "
        f"Allowed section fields: {json.dumps(section_fields)}"
    )
    payload = {
        "model": settings.OPENAI_ASSISTANT_MODEL,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "inventory_record_preview",
                "strict": True,
                "schema": schema,
            }
        },
        "safety_identifier": safety_identifier,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=settings.OPENAI_ASSISTANT_TIMEOUT,
        ) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message")
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = None
        raise AssistantError(detail or "The assistant service rejected the request.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AssistantError("The assistant service is temporarily unavailable.") from exc

    try:
        result = json.loads(_extract_output_text(parsed))
    except (json.JSONDecodeError, TypeError) as exc:
        raise AssistantError("The assistant returned an invalid response.") from exc
    section = result.get("section")
    if section not in TAB_ORDER:
        raise AssistantError("The assistant did not select a valid inventory section.")
    allowed = set(section_fields[section])
    row = {}
    for field in result.get("fields", []):
        name = str(field.get("name") or "")
        if name in allowed:
            row[name] = str(field.get("value") or "")
    return {
        "section": section,
        "section_label": get_spec(section)["tab_label"],
        "row": row,
        "summary": str(result.get("summary") or ""),
    }
