import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Project, TabRecord, FrameRangeAssignment
from .forms import FrameRangeAssignmentForm

class FileScopedFrameTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.user=User.objects.create_user('file-a')
        self.other=User.objects.create_user('file-b')
        self.admin=User.objects.create_superuser('file-admin','admin@example.com','test-pass')
        self.project=Project.objects.create(name='File scopes',code='file-scopes')
        self.project.members.add(self.user,self.other)
    def test_files_are_independent_in_all_inventory_types(self):
        for tab in ('sign','pavement','lane','curb'):
            for index,source in enumerate(('FRONT_014103_out.csv','FRONT_014104_out.csv'),1):
                TabRecord.objects.create(project=self.project,tab=tab,tab_record_id=index,data={'_AI_PROCESSED':True,'FRAME':'42','_AI_SOURCE_FILE':source})
            a=FrameRangeAssignment(project=self.project,user=self.user,tab=tab,source_file='FRONT_014103_out.csv',start_frame=1,end_frame=50)
            a.full_clean();a.save()
            form=FrameRangeAssignmentForm(project=self.project,data={'tab':tab,'source_file':'FRONT_014104_out.csv','user':self.other.pk,'start_frame':42,'end_frame':42})
            self.assertTrue(form.is_valid(),form.errors)
            self.assertIn('FRONT_014104_out.csv',dict(form.fields['start_frame'].choices)[42])
            form.save()
            clash=FrameRangeAssignment(project=self.project,user=self.other,tab=tab,source_file=a.source_file,start_frame=40,end_frame=50)
            with self.assertRaises(ValidationError):clash.full_clean()
            self.client.force_login(self.user)
            rows=self.client.get(f'/api/{tab}/ai-processed').json()['records']
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['SOURCE_FILE'],'FRONT_014103_out.csv')
            self.assertEqual(self.client.delete(f'/api/{tab}/records/2').status_code,404)
            self.client.force_login(self.admin)
            rows=self.client.get(f'/api/{tab}/ai-processed').json()['records']
            self.assertEqual({r['SOURCE_FILE']:r['ASSIGNMENT_STATUS'] for r in rows},{'FRONT_014103_out.csv':'file-a','FRONT_014104_out.csv':'file-b'})
    def test_reimport_identity_includes_filename(self):
        self.client.force_login(self.admin)
        session=self.client.session;session['inventory_project_id']=self.project.pk;session.save()
        content=b'Frame,Latitude,Longitude,Elevation,IMAGE,CODE\n42,37,-122,10,image.jpg,R1-1\n'
        url=reverse('admin:inventory_tabrecord_import_ai_processed')
        for name in ('A.csv','B.csv','A.csv'):
            response=self.client.post(url,{'section':'sign','excluded_codes':'NULL','data_file':SimpleUploadedFile(name,content)})
            self.assertEqual(response.status_code,302)
        self.assertEqual(TabRecord.objects.count(),2)
        self.assertEqual(set(TabRecord.objects.values_list('source_file',flat=True)),{'A.csv','B.csv'})

    def test_legacy_migration_preserves_existing_file_access(self):
        import importlib
        from django.apps import apps
        from django.db import connection
        for index,source in enumerate(('A.csv','B.csv'),1):
            TabRecord.objects.create(project=self.project,tab='sign',tab_record_id=index,data={'_AI_PROCESSED':True,'FRAME':'42','_AI_SOURCE_FILE':source})
        TabRecord.objects.update(source_file='')
        FrameRangeAssignment.objects.create(project=self.project,user=self.user,start_frame=1,end_frame=50)
        migration=importlib.import_module('inventory.migrations.0023_scope_existing_frame_assignments')
        from types import SimpleNamespace
        migration.scope_existing(apps,SimpleNamespace(connection=connection))
        self.assertEqual(set(FrameRangeAssignment.objects.values_list('source_file',flat=True)),{'A.csv','B.csv'})
        self.assertEqual(set(TabRecord.objects.values_list('source_file',flat=True)),{'A.csv','B.csv'})
