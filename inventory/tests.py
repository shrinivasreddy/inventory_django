import re

from django.core import mail
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username="inventoryuser",
            email="existing@example.com",
            password="StrongPass!234",
        )

    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

        response = self.client.get(reverse("api_spec", args=["sign"]))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Authentication required."})

    def test_login_grants_access_and_logout_revokes_it(self):
        response = self.client.get(reverse("login"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("login"),
            {"username": "inventoryuser", "password": "StrongPass!234"},
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

        csrf = self.client.cookies["csrftoken"].value
        response = self.client.post(
            reverse("logout"), HTTP_X_CSRFTOKEN=csrf
        )
        self.assertRedirects(response, reverse("login"))
        self.assertEqual(self.client.get(reverse("home")).status_code, 302)

    def test_signup_creates_database_user_and_logs_them_in(self):
        response = self.client.get(reverse("signup"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "AnotherStrong!234",
                "password2": "AnotherStrong!234",
            },
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertRedirects(response, reverse("home"))
        self.assertTrue(User.objects.filter(username="newuser", email="new@example.com").exists())
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_duplicate_email_is_rejected(self):
        response = self.client.get(reverse("signup"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("signup"),
            {
                "username": "anotheruser",
                "email": "EXISTING@example.com",
                "password1": "AnotherStrong!234",
                "password2": "AnotherStrong!234",
            },
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertFalse(User.objects.filter(username="anotheruser").exists())

    def test_signup_rejects_email_without_valid_domain_pattern(self):
        response = self.client.get(reverse("signup"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("signup"),
            {
                "username": "invalidemailuser",
                "email": "person@localhost",
                "password1": "AnotherStrong!234",
                "password2": "AnotherStrong!234",
            },
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")
        self.assertFalse(User.objects.filter(username="invalidemailuser").exists())

    def test_password_requirement_endpoint_uses_django_validators(self):
        response = self.client.get(reverse("signup"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("password_requirements"),
            data=(
                '{"username":"newuser","email":"new@example.com",'
                '"password":"newuser123"}'
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        checks = response.json()["checks"]
        self.assertFalse(checks["UserAttributeSimilarityValidator"])
        self.assertTrue(checks["MinimumLengthValidator"])
        self.assertTrue(checks["NumericPasswordValidator"])

        response = self.client.post(
            reverse("password_requirements"),
            data='{"username":"newuser","email":"new@example.com","password":"12345678"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        checks = response.json()["checks"]
        self.assertFalse(checks["NumericPasswordValidator"])
        self.assertFalse(checks["CommonPasswordValidator"])

    def test_write_api_requires_csrf_token(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("api_records", args=["sign"]),
            data='{"row": {}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_endpoints_reject_unsupported_methods(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        csrf = response.cookies["csrftoken"].value
        self.assertEqual(
            self.client.post(reverse("home"), HTTP_X_CSRFTOKEN=csrf).status_code,
            405,
        )
        self.assertEqual(
            self.client.post(
                reverse("api_spec", args=["sign"]),
                HTTP_X_CSRFTOKEN=csrf,
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.post(
                reverse("api_export_all"),
                HTTP_X_CSRFTOKEN=csrf,
            ).status_code,
            405,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_changes_password_with_single_use_token(self):
        response = self.client.get(reverse("password_reset"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("password_reset"),
            {"email": "existing@example.com"},
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Bluedome Inventory")
        self.assertNotIn("StrongPass!234", mail.outbox[0].body)

        match = re.search(r"http://testserver(\S+)", mail.outbox[0].body)
        self.assertIsNotNone(match)
        token_url = match.group(1)

        response = self.client.get(token_url)
        self.assertEqual(response.status_code, 302)
        set_password_url = response.url
        response = self.client.get(set_password_url)
        self.assertEqual(response.status_code, 200)

        csrf = self.client.cookies["csrftoken"].value
        response = self.client.post(
            set_password_url,
            {
                "new_password1": "ReplacementPass!456",
                "new_password2": "ReplacementPass!456",
            },
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertRedirects(response, reverse("password_reset_complete"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ReplacementPass!456"))
        self.assertFalse(self.user.check_password("StrongPass!234"))

        response = self.client.get(token_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Link expired")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_does_not_reveal_unknown_email(self):
        response = self.client.get(reverse("password_reset"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("password_reset"),
            {"email": "unknown@example.com"},
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_rejects_invalid_email_pattern(self):
        response = self.client.get(reverse("password_reset"))
        csrf = response.cookies["csrftoken"].value
        response = self.client.post(
            reverse("password_reset"),
            {"email": "person@localhost"},
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")
        self.assertEqual(len(mail.outbox), 0)
