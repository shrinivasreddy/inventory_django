from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def clear_existing_inventory(apps, schema_editor):
    apps.get_model("inventory", "TabRecord").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventory", "0007_move_image_link_to_last_column"),
    ]

    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("code", models.SlugField(max_length=50, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("members", models.ManyToManyField(blank=True, related_name="inventory_projects", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.RunPython(clear_existing_inventory, migrations.RunPython.noop),
        migrations.AddField(
            model_name="tabrecord",
            name="project",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_records", to="inventory.project"),
        ),
        migrations.AlterField(
            model_name="tabrecord",
            name="project",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_records", to="inventory.project"),
        ),
        migrations.AddIndex(
            model_name="tabrecord",
            index=models.Index(fields=["project", "tab"], name="inventory_project_tab_idx"),
        ),
    ]
