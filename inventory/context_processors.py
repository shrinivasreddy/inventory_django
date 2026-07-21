from django.conf import settings

from .models import TabRecord


def admin_inventory_records(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
    admin_path = f"/{settings.ADMIN_URL.strip('/')}/"
    if not request.path.startswith(admin_path):
        return {}
    records = list(
        TabRecord.objects.select_related("owner").order_by("-created_at")[:50]
    )
    return {"admin_inventory_records": records}
