# accounts/tests/test_admin_action_logs_api_view.py
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile, employee_model, AdminActionLog

User = get_user_model()


class AdminActionLogsAPITests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="Password123!",
            first_name="Root",
            last_name="Admin",
        )

        profile = Profile.objects.create(name="Cuentas", permissions=["customers.manage"])
        self.employee = User.objects.create_user(
            email="employee@example.com",
            password="Password123!",
            first_name="Regular",
            last_name="Employee",
            role="employee",
        )
        employee_model.objects.create(user=self.employee, profile=profile)

        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Password123!",
            first_name="Jane",
            last_name="Doe",
            role="customer",
        )

        self.older_log = AdminActionLog.objects.create(
            performed_by=self.superuser,
            target_user=self.customer,
            changes={"matricula": {"old": None, "new": "A12345"}},
        )
        self.newer_log = AdminActionLog.objects.create(
            performed_by=self.superuser,
            target_user=self.customer,
            changes={"password": {"changed": True}},
        )

        self.url = reverse("api:admin-user-action-logs")

    def test_rejects_non_superuser(self):
        self.client.force_authenticate(self.employee)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allows_superuser(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 2)

        rows = response.data["data"]
        self.assertEqual(rows[0]["id"], self.newer_log.id)  # ordered -created_at
        self.assertEqual(rows[1]["id"], self.older_log.id)

        first = rows[0]
        self.assertEqual(first["performed_by"]["email"], self.superuser.email)
        self.assertEqual(first["target_user"]["email"], self.customer.email)
        self.assertEqual(first["changes"], {"password": {"changed": True}})


class UserDetailsPatchAuditTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="Password123!",
            first_name="Root",
            last_name="Admin",
        )

        profile = Profile.objects.create(name="Cuentas", permissions=["customers.manage"])
        self.employee = User.objects.create_user(
            email="employee@example.com",
            password="Password123!",
            first_name="Regular",
            last_name="Employee",
            role="employee",
        )
        employee_model.objects.create(user=self.employee, profile=profile)

        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Password123!",
            first_name="Jane",
            last_name="Doe",
            role="customer",
        )

        self.url = reverse("api:admin-user-detail", kwargs={"id": self.customer.id})

    def test_non_superuser_cannot_change_email(self):
        self.client.force_authenticate(self.employee)
        response = self.client.patch(self.url, {"email": "new@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(AdminActionLog.objects.count(), 0)

    def test_superuser_can_change_identity_fields_and_it_is_logged(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            self.url,
            {
                "email": "new@example.com",
                "first_name": "Janet",
                "last_name": "Smith",
                "matricula": "B67890",
                "password": "AnotherStrongPass456",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "new@example.com")
        self.assertEqual(self.customer.first_name, "Janet")
        self.assertEqual(self.customer.last_name, "Smith")
        self.assertEqual(self.customer.matricula, "B67890")
        self.assertTrue(self.customer.check_password("AnotherStrongPass456"))

        self.assertEqual(AdminActionLog.objects.count(), 1)
        log = AdminActionLog.objects.first()
        self.assertEqual(log.performed_by, self.superuser)
        self.assertEqual(log.target_user, self.customer)
        self.assertEqual(log.changes["email"], {"old": "customer@example.com", "new": "new@example.com"})
        self.assertEqual(log.changes["password"], {"changed": True})
        self.assertNotIn("AnotherStrongPass456", str(log.changes))

    def test_status_only_changes_are_not_logged(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(self.url, {"is_active": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AdminActionLog.objects.count(), 0)
