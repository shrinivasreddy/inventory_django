import io
import json
import re
from unittest.mock import patch

from django.core import mail
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from .models import DropdownOption, InventorySection, MutcdMapping, TabRecord


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
        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, "MM-DD-YYYY")
        self.assertContains(home_response, "date-picker-btn")
        self.assertContains(home_response, "Choose date")
        self.assertContains(home_response, "saveCurrentDraft")
        self.assertContains(home_response, "restoreCurrentDraft")
        self.assertNotContains(home_response, "clearForm(true)")

    def test_assistant_preview_requires_authentication(self):
        csrf = self.client.get(reverse("login")).cookies["csrftoken"].value
        response = self.client.post(
            reverse("api_assistant_preview"),
            data='{"prompt":"add a sign"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 401)

    @patch("inventory.views.interpret_inventory_prompt")
    def test_authenticated_user_can_preview_without_saving(self, interpret):
        interpret.return_value = {
            "section": "sign",
            "section_label": "Sign Inventory",
            "row": {"ST_ID": "100", "POLE_ID": "P2", "SIGN": "R1-1"},
            "summary": "Add one sign record.",
        }
        self.client.force_login(self.user)
        csrf = self.client.get(reverse("home")).cookies["csrftoken"].value
        response = self.client.post(
            reverse("api_assistant_preview"),
            data='{"prompt":"add sign 100 pole P2 R1-1"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["section"], "sign")
        self.assertEqual(response.json()["row"]["SIGN_UID"], "SR_100_P2_R1-1")
        self.assertEqual(TabRecord.objects.count(), 0)

    def test_assistant_rejects_empty_prompt(self):
        self.client.force_login(self.user)
        csrf = self.client.get(reverse("home")).cookies["csrftoken"].value
        response = self.client.post(
            reverse("api_assistant_preview"),
            data='{"prompt":"  "}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 400)

    @patch("inventory.views.transcribe_audio", return_value="Add sign record ST ID 100")
    def test_authenticated_user_can_transcribe_voice(self, transcribe):
        self.client.force_login(self.user)
        csrf = self.client.get(reverse("home")).cookies["csrftoken"].value
        audio = SimpleUploadedFile(
            "voice.webm",
            b"test-audio",
            content_type="audio/webm",
        )
        response = self.client.post(
            reverse("api_assistant_transcribe"),
            {"audio": audio},
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Add sign record ST ID 100")
        transcribe.assert_called_once()

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


class DatabaseConfigurationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="regularuser",
            password="StrongPass!234",
        )
        self.admin_user = User.objects.create_superuser(
            username="sectionadmin",
            email="admin@example.com",
            password="StrongPass!234",
        )

    def test_runtime_options_come_from_database(self):
        section = InventorySection.objects.get(key="sign")
        DropdownOption.objects.create(
            section=section,
            field_name="SIGN_CONDITION",
            value="ADMIN ADDED VALUE",
            sort_order=999,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("api_spec", args=["sign"]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "ADMIN ADDED VALUE",
            response.json()["options"]["SIGN_CONDITION"],
        )

    def test_regular_users_only_see_and_manage_their_own_inventory(self):
        other_user = User.objects.create_user(
            username="otheruser",
            password="StrongPass!234",
        )
        own = TabRecord.objects.create(
            owner=self.user,
            tab="sign",
            tab_record_id=1,
            data={"ST_ID": "100", "POLE_ID": "P1", "SIGN": "S1"},
        )
        other = TabRecord.objects.create(
            owner=other_user,
            tab="sign",
            tab_record_id=2,
            data={"ST_ID": "200", "POLE_ID": "P2", "SIGN": "S2"},
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("api_records", args=["sign"]))
        self.assertEqual([row["ID"] for row in response.json()["records"]], [own.tab_record_id])

        response = self.client.delete(
            reverse("api_record_detail", args=["sign", other.tab_record_id])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(TabRecord.objects.filter(pk=other.pk).exists())

        response = self.client.delete(reverse("api_records", args=["sign"]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TabRecord.objects.filter(pk=own.pk).exists())
        self.assertTrue(TabRecord.objects.filter(pk=other.pk).exists())

    def test_admin_sees_all_inventory_with_owner_labels(self):
        other_user = User.objects.create_user(
            username="fieldworker",
            first_name="Field",
            last_name="Worker",
            password="StrongPass!234",
        )
        TabRecord.objects.create(
            owner=self.user,
            tab="sign",
            tab_record_id=1,
            data={"ST_ID": "100", "POLE_ID": "P1", "SIGN": "S1"},
        )
        TabRecord.objects.create(
            owner=other_user,
            tab="sign",
            tab_record_id=2,
            data={"ST_ID": "200", "POLE_ID": "P2", "SIGN": "S2"},
        )
        self.client.force_login(self.admin_user)
        spec_response = self.client.get(reverse("api_spec", args=["sign"]))
        self.assertNotIn("ADDED_BY", spec_response.json()["columns"])
        response = self.client.get(reverse("api_records", args=["sign"]))
        records = response.json()["records"]
        self.assertEqual(len(records), 2)
        self.assertNotIn("ADDED_BY", records[0])
        self.assertNotIn("ADDED_BY", records[1])

        admin_response = self.client.get(
            reverse("admin:inventory_tabrecord_changelist")
        )
        self.assertContains(admin_response, "Username")
        self.assertContains(admin_response, "Field Worker")
        self.assertContains(admin_response, "Date")

        dashboard_response = self.client.get(reverse("admin:index"))
        self.assertContains(dashboard_response, "Inventory Records")
        self.assertContains(dashboard_response, "Field Worker")
        self.assertContains(dashboard_response, ">1</a>", html=False)
        self.assertContains(dashboard_response, "Section")
        self.assertContains(dashboard_response, "Date added")
        self.assertContains(
            dashboard_response,
            TabRecord.objects.order_by("pk").first().created_at.strftime("%m-%d-%Y"),
        )

        self.assertContains(admin_response, "By Username")
        self.assertContains(admin_response, "By Inventory section")
        username_response = self.client.get(
            reverse("admin:inventory_tabrecord_changelist"),
            {"username": other_user.pk},
        )
        self.assertContains(username_response, "Field Worker")
        self.assertEqual(username_response.context["cl"].result_count, 1)
        section_response = self.client.get(
            reverse("admin:inventory_tabrecord_changelist"),
            {"inventory_section": "sign"},
        )
        self.assertEqual(section_response.context["cl"].result_count, 2)
        section_filter = next(
            spec
            for spec in section_response.context["cl"].filter_specs
            if spec.title == "Inventory section"
        )
        sign_choices = [
            choice for choice in section_filter.lookup_choices if choice[0] == "sign"
        ]
        self.assertEqual(len(sign_choices), 1)

    def test_new_inventory_record_is_assigned_to_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("api_records", args=["sign"]),
            data=json.dumps({
                "row": {"ST_ID": "100", "POLE_ID": "P1", "SIGN": "S1"}
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TabRecord.objects.get().owner, self.user)

    def test_inventory_dates_require_mm_dd_yyyy(self):
        self.client.force_login(self.user)
        row = {
            "ST_ID": "100",
            "POLE_ID": "P1",
            "SIGN": "S1",
            "INSP_DATE": "21-07-2026",
        }
        response = self.client.post(
            reverse("api_records", args=["sign"]),
            data=json.dumps({"row": row}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("MM-DD-YYYY", response.json()["error"])

        row["INSP_DATE"] = "07-21-2026"
        response = self.client.post(
            reverse("api_records", args=["sign"]),
            data=json.dumps({"row": row}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TabRecord.objects.get().data["INSP_DATE"], "07-21-2026")

    def test_coordinates_are_rounded_to_seven_decimal_places(self):
        self.client.force_login(self.user)
        row = {
            "ST_ID": "100",
            "POLE_ID": "P1",
            "SIGN": "S1",
            "LATITUDE": "12.34567894",
            "LONGITUDE": "-98.76543216",
        }
        response = self.client.post(
            reverse("api_records", args=["sign"]),
            data=json.dumps({"row": row}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        stored = TabRecord.objects.get().data
        self.assertEqual(stored["LATITUDE"], "12.3456789")
        self.assertEqual(stored["LONGITUDE"], "-98.7654322")

        row["LATITUDE"] = "91.0000000"
        response = self.client.post(
            reverse("api_records", args=["sign"]),
            data=json.dumps({"row": row}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("between -90 and 90", response.json()["error"])

    def test_admin_mutcd_mapping_populates_both_database_dropdowns(self):
        section = InventorySection.objects.get(key="sign")
        MutcdMapping.objects.create(
            section=section,
            word_description="testdesc",
            mutcd_code="testcode",
            classification="testcl",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("api_spec", args=["sign"]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("testcode", data["options"]["MUTCD"])
        self.assertIn("testdesc", data["options"]["WORD_DESCRIPTION"])
        self.assertEqual(data["mutcd_to_class"]["testcode"], "testcl")
        self.assertEqual(data["mutcd_map"]["testdesc"]["MUTCD"], "testcode")
        self.assertIn("no-store", response["Cache-Control"])

    def test_all_database_dropdown_values_are_alphabetically_sorted(self):
        self.client.force_login(self.user)
        for section_key in ("sign", "pavement", "lane", "curb"):
            response = self.client.get(reverse("api_spec", args=[section_key]))
            self.assertEqual(response.status_code, 200)
            for field_name, values in response.json()["options"].items():
                self.assertEqual(
                    values,
                    sorted(values, key=lambda value: str(value).casefold()),
                    msg=f"{section_key}.{field_name} is not alphabetically sorted",
                )

    def test_only_admin_role_can_open_configuration_admin(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("admin:inventory_dropdownoption_changelist")
            ).status_code,
            200,
        )

    def test_admin_pages_use_bluedome_branding(self):
        login_response = self.client.get(reverse("admin:login"))
        self.assertContains(login_response, "Bluedome Inventory")
        self.assertNotContains(login_response, "Django administration")

        self.client.force_login(self.admin_user)
        index_response = self.client.get(reverse("admin:index"))
        self.assertContains(index_response, "Bluedome Inventory")
        self.assertContains(index_response, "Inventory Configuration")
        self.assertNotContains(index_response, "Django administration")

    def test_configuration_rows_have_edit_and_delete_actions(self):
        self.client.force_login(self.admin_user)
        option = DropdownOption.objects.create(
            section_id="sign",
            field_name="SIGN_CONDITION",
            value="ROW ACTION TEST VALUE",
            sort_order=9999,
        )
        response = self.client.get(
            reverse("admin:inventory_dropdownoption_changelist"),
            {"q": "ROW ACTION TEST VALUE"},
        )
        self.assertContains(
            response,
            reverse(
                "admin:inventory_dropdownoption_change",
                args=[option.pk],
            ),
        )
        self.assertContains(
            response,
            reverse(
                "admin:inventory_dropdownoption_delete",
                args=[option.pk],
            ),
        )
        self.assertContains(response, "Edit")
        self.assertContains(response, "Delete")
        self.assertContains(response, 'aria-label="Edit"')
        self.assertContains(response, 'aria-label="Delete"')

        change_response = self.client.get(
            reverse("admin:inventory_dropdownoption_change", args=[option.pk])
        )
        self.assertContains(change_response, "icon-delete")
        self.assertContains(change_response, "<svg", html=False)

    def test_admin_can_delete_mutcd_mapping_with_confirmation(self):
        mapping = MutcdMapping.objects.create(
            section_id="sign",
            word_description="DELETE TEST DESCRIPTION",
            mutcd_code="DELETE-TEST-CODE",
            classification="TEST",
        )
        self.client.force_login(self.admin_user)
        delete_url = reverse(
            "admin:inventory_mutcdmapping_delete",
            args=[mapping.pk],
        )
        confirmation = self.client.get(delete_url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Delete mutcd mapping?")
        self.assertContains(confirmation, "Delete permanently")
        self.assertContains(confirmation, "button-danger")
        self.assertContains(confirmation, "button-secondary")

        response = self.client.post(delete_url, {"post": "yes"})
        self.assertRedirects(
            response,
            reverse("admin:inventory_mutcdmapping_changelist"),
        )
        self.assertFalse(MutcdMapping.objects.filter(pk=mapping.pk).exists())

    @staticmethod
    def _excel_upload(section_key, rows):
        from .specs import get_spec

        spec = get_spec(section_key)
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(spec["columns"])
        for values in rows:
            worksheet.append([values.get(column, "") for column in spec["columns"]])
        buffer = io.BytesIO()
        workbook.save(buffer)
        return SimpleUploadedFile(
            "inventory-import.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_admin_can_bulk_import_valid_excel_records(self):
        self.client.force_login(self.admin_user)
        upload = self._excel_upload(
            "sign",
            [
                {"ST_ID": "100", "POLE_ID": "P1", "SIGN": "S1", "STREET_NAME": "FIRST ST"},
                {"ST_ID": "100", "POLE_ID": "P2", "SIGN": "S2", "STREET_NAME": "SECOND ST"},
            ],
        )
        response = self.client.post(
            reverse("admin:inventory_tabrecord_import_excel"),
            {"section": "sign", "excel_file": upload},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Successfully imported 2 Sign Inventory records")
        imported = list(TabRecord.objects.filter(tab="sign").order_by("tab_record_id"))
        self.assertEqual(len(imported), 2)
        self.assertEqual(imported[0].data["SIGN_UID"], "SR_100_P1_S1")
        self.assertEqual(imported[1].data["SIGN_UID"], "SR_100_P2_S2")

    def test_admin_can_bulk_import_mutcd_mappings(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Section", "Word description", "MUTCD code", "Classification"])
        worksheet.append(["sign", "Bulk sign one", "B-1", "Warning"])
        worksheet.append(["sign", "Bulk sign two", "B-2", "Regulatory"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        upload = SimpleUploadedFile(
            "mutcd-mappings.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("admin:inventory_mutcdmapping_import_excel"),
            {"excel_file": upload},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Successfully imported 2 mutcd mappings")
        self.assertTrue(
            MutcdMapping.objects.filter(
                section_id="sign",
                word_description="Bulk sign one",
                mutcd_code="B-1",
            ).exists()
        )

    def test_empty_configuration_workbook_is_rejected(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Section", "Word description", "MUTCD code", "Classification"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        upload = SimpleUploadedFile(
            "empty-mutcd-mappings.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("admin:inventory_mutcdmapping_import_excel"),
            {"excel_file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The workbook does not contain any data rows.")

    def test_mutcd_mapping_admin_shows_bulk_excel_controls(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("admin:inventory_mutcdmapping_changelist")
        )
        self.assertContains(response, "Import Excel")
        self.assertContains(response, "Download Template")
        self.assertContains(response, "Export All")
        add_response = self.client.get(
            reverse("admin:inventory_mutcdmapping_add")
        )
        self.assertContains(add_response, "Import Multiple via Excel")
        import_response = self.client.get(
            reverse("admin:inventory_mutcdmapping_import_excel")
        )
        self.assertContains(import_response, "Export All Data")
        self.assertContains(
            import_response,
            reverse("admin:inventory_mutcdmapping_export_excel"),
        )

    def test_invalid_excel_import_is_atomic(self):
        self.client.force_login(self.admin_user)
        upload = self._excel_upload(
            "sign",
            [
                {"ST_ID": "100", "POLE_ID": "P1", "SIGN": "S1"},
                {"ST_ID": "100", "POLE_ID": "", "SIGN": "S2"},
            ],
        )
        response = self.client.post(
            reverse("admin:inventory_tabrecord_import_excel"),
            {"section": "sign", "excel_file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Row 3: missing required values POLE_ID")
        self.assertEqual(TabRecord.objects.filter(tab="sign").count(), 0)

    def test_admin_excel_template_and_full_export(self):
        self.client.force_login(self.admin_user)
        template_response = self.client.get(
            reverse("admin:inventory_tabrecord_excel_template")
        )
        self.assertEqual(template_response.status_code, 200)
        template_book = load_workbook(io.BytesIO(template_response.content), read_only=True)
        self.assertEqual(
            template_book.sheetnames,
            ["Sign Inventory", "Pavement Inventory", "Lane Inventory", "Curb Inventory"],
        )
        self.assertEqual(template_book["Sign Inventory"]["A1"].value, "ID")

        TabRecord.objects.create(
            tab="sign",
            tab_record_id=1,
            data={"ST_ID": "100", "POLE_ID": "P1", "SIGN": "S1", "SIGN_UID": "SR_100_P1_S1"},
        )
        export_response = self.client.get(
            reverse("admin:inventory_tabrecord_export_excel")
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response["X-Record-Count"], "1")
        export_book = load_workbook(io.BytesIO(export_response.content), read_only=True)
        sign_sheet = export_book["Sign Inventory"]
        self.assertEqual(sign_sheet["A2"].value, 1)
        self.assertEqual(sign_sheet["B2"].value, "100")

    def test_regular_user_cannot_access_admin_excel_tools(self):
        self.client.force_login(self.user)
        for url_name in (
            "admin:inventory_tabrecord_import_excel",
            "admin:inventory_tabrecord_excel_template",
            "admin:inventory_tabrecord_export_excel",
        ):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302)

    def test_only_admin_role_can_add_reference_options(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("api_options", args=["sign"]),
            data='{"field":"SIGN_CONDITION","value":"UNAUTHORIZED VALUE"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            DropdownOption.objects.filter(value="UNAUTHORIZED VALUE").exists()
        )

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("api_options", args=["sign"]),
            data='{"field":"SIGN_CONDITION","value":"AUTHORIZED VALUE"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            DropdownOption.objects.filter(value="AUTHORIZED VALUE").exists()
        )

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
