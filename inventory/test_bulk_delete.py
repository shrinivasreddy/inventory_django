import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Project, TabRecord


class BulkDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bulk-user")
        self.other = User.objects.create_user(username="bulk-other")
        self.project = Project.objects.create(name="Bulk", code="bulk")
        self.project.members.add(self.user)
        self.client.force_login(self.user)
        session = self.client.session
        session["inventory_project_id"] = self.project.pk
        session.save()
        for record_id in (1, 2, 3):
            TabRecord.objects.create(project=self.project, owner=self.user,
                                     tab="sign", tab_record_id=record_id, data={})

    def delete(self, ids):
        return self.client.delete(reverse("api_records", args=["sign"]),
                                  data=json.dumps({"ids": ids}), content_type="application/json")

    def test_deletes_only_selected_records(self):
        self.assertEqual(self.delete([1, 3]).status_code, 200)
        self.assertEqual(list(TabRecord.objects.values_list("tab_record_id", flat=True)), [2])

    def test_forbidden_selection_deletes_nothing(self):
        TabRecord.objects.filter(tab_record_id=3).update(owner=self.other)
        self.assertEqual(self.delete([1, 3]).status_code, 403)
        self.assertEqual(TabRecord.objects.count(), 3)

    def test_other_project_selection_deletes_nothing(self):
        project = Project.objects.create(name="Other", code="other")
        TabRecord.objects.filter(tab_record_id=3).update(project=project)
        self.assertEqual(self.delete([1, 3]).status_code, 403)
        self.assertEqual(TabRecord.objects.count(), 3)

    def test_empty_or_invalid_selection_never_clears_inventory(self):
        for ids in ([], [True], ["1"], [-1], None):
            self.assertEqual(self.delete(ids).status_code, 400)
        self.assertEqual(TabRecord.objects.count(), 3)
