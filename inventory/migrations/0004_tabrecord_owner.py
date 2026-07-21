from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventory", "0003_seed_database_configuration"),
    ]

    operations = [
        migrations.AddField(
            model_name="tabrecord",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inventory_records",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="tabrecord",
            index=models.Index(fields=["owner", "tab"], name="inventory_owner_tab_idx"),
        ),
    ]
