from django.db import migrations


def scope_existing(apps, schema_editor):
    Record = apps.get_model('inventory', 'TabRecord')
    Assignment = apps.get_model('inventory', 'FrameRangeAssignment')
    alias = schema_editor.connection.alias
    for record in Record.objects.using(alias).filter(is_ai_processed=True).iterator():
        Record.objects.using(alias).filter(pk=record.pk).update(source_file=str((record.data or {}).get('_AI_SOURCE_FILE', '') or '')[:255])
    for assignment in list(Assignment.objects.using(alias).all()):
        scopes = list(Record.objects.using(alias).filter(project_id=assignment.project_id, is_ai_processed=True, ai_frame__gte=assignment.start_frame, ai_frame__lte=assignment.end_frame).order_by().values_list('tab', 'source_file').distinct())
        for index, (tab, source) in enumerate(scopes):
            if index == 0:
                Assignment.objects.using(alias).filter(pk=assignment.pk).update(tab=tab, source_file=source)
            else:
                Assignment.objects.using(alias).create(project_id=assignment.project_id,user_id=assignment.user_id,tab=tab,source_file=source,start_frame=assignment.start_frame,end_frame=assignment.end_frame)


class Migration(migrations.Migration):
    dependencies = [('inventory', '0022_remove_framerangeassignment_unique_project_user_frame_range_and_more')]
    operations = [migrations.RunPython(scope_existing, migrations.RunPython.noop)]
