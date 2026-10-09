from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, RequestFactory
from django.urls import reverse
from .middleware import AuthenticationRateLimitMiddleware


class SecurityReviewTests(TestCase):
    def test_staff_without_permissions_cannot_use_custom_admin_endpoints(self):
        user = get_user_model().objects.create_user('limited-staff', is_staff=True)
        self.client.force_login(user)
        for name in ['auth_user_pending_approvals', 'auth_user_pending_approval_count',
                     'inventory_tabrecord_import_ai_processed', 'inventory_tabrecord_ai_filter_settings',
                     'inventory_tabrecord_export_excel', 'inventory_tabrecord_excel_template']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse('admin:' + name)).status_code, 403)

    def test_authentication_throttle_expires_and_ignores_forwarded_ip(self):
        cache.clear()
        self.addCleanup(cache.clear)
        middleware = AuthenticationRateLimitMiddleware(lambda request: None)
        request = RequestFactory().post('/login/', {'username':'user'}, REMOTE_ADDR='192.0.2.5')
        request.resolver_match = SimpleNamespace(url_name='login')
        with patch('inventory.middleware.time.time', return_value=3000):
            for _ in range(15):
                self.assertIsNone(middleware.process_view(request, None, (), {}))
            request.META['HTTP_X_FORWARDED_FOR'] = '192.0.2.6'
            response = middleware.process_view(request, None, (), {})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response['Retry-After'], '300')
        with patch('inventory.middleware.time.time', return_value=3300):
            self.assertIsNone(middleware.process_view(request, None, (), {}))
