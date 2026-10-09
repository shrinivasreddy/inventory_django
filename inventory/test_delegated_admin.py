from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, RequestFactory
from django.urls import reverse
from unittest.mock import patch
from .models import UserProfile, Project


class DelegatedAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser('owner', password='test-password')
        self.delegate = User.objects.create_user('delegate', password='test-password')
        self.regular = User.objects.create_user('regular', password='test-password')
        self.admin = admin.site._registry[User]
        self.request = RequestFactory().post('/')
        self.request.user = self.owner

    def grant(self):
        with patch.object(self.admin, 'message_user'):
            self.admin.grant_admin_access(self.request, get_user_model().objects.filter(pk=self.delegate.pk))
        self.delegate.refresh_from_db()

    def test_grant_protection_and_revocation(self):
        self.grant()
        self.assertTrue(self.delegate.is_superuser and self.delegate.is_staff)
        self.assertTrue(UserProfile.objects.get(user=self.delegate).delegated_admin)
        self.client.force_login(self.delegate)
        self.assertEqual(self.client.get(reverse('admin:inventory_project_add')).status_code, 200)
        for suffix in ('change', 'delete', 'password'):
            response = self.client.post(f'/admin/auth/user/{self.owner.pk}/{suffix}/', {'is_active':'', 'is_superuser':''})
            self.assertEqual(response.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_superuser and self.owner.is_active)
        self.assertEqual(self.client.post(reverse('admin:auth_user_deactivate_account', args=[self.owner.pk])).status_code, 403)
        self.request.user = self.delegate
        self.assertFalse(self.admin.has_change_permission(self.request, self.owner))
        self.assertTrue(self.admin.has_change_permission(self.request, self.regular))
        self.assertIn('is_superuser', self.admin.get_readonly_fields(self.request, self.regular))
        with self.assertRaises(PermissionDenied):
            self.admin.grant_admin_access(self.request, get_user_model().objects.filter(pk=self.regular.pk))
        with self.assertRaises(PermissionDenied):
            self.admin.delete_queryset(self.request, get_user_model().objects.filter(pk=self.owner.pk))
        self.request.user = self.owner
        with patch.object(self.admin, 'message_user'):
            self.admin.revoke_admin_access(self.request, get_user_model().objects.filter(pk=self.delegate.pk))
        self.delegate.refresh_from_db()
        self.assertFalse(self.delegate.is_staff or self.delegate.is_superuser)
        self.assertTrue(self.delegate.is_active)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)
