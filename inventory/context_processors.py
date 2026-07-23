from django.conf import settings

from .models import TabRecord
from .views import selected_project


def admin_inventory_records(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
    admin_path = f"/{settings.ADMIN_URL.strip('/')}/"
    if not request.path.startswith(admin_path):
        return {}
    project = selected_project(request)
    records = list(
        TabRecord.objects.filter(project=project).select_related("owner").order_by("-created_at")[:50]
    ) if project else []
    return {"admin_inventory_records": records, "admin_selected_project": project}
