from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AccountPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='account-user',
            password='StrongPass123!',
        )

    def test_settings_requires_login(self):
        response = self.client.get(
            reverse('accounts:settings')
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse('accounts:login'),
            response.url,
        )

    def test_settings_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('accounts:settings')
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Account preferences',
        )

    def test_private_profile_is_hidden_from_anonymous_user(self):
        self.user.profile.is_public = False
        self.user.profile.save(
            update_fields=['is_public']
        )

        response = self.client.get(
            reverse(
                'accounts:public_profile',
                args=[self.user.username],
            )
        )

        self.assertEqual(response.status_code, 302)

    def test_owner_can_view_private_profile(self):
        self.user.profile.is_public = False
        self.user.profile.save(
            update_fields=['is_public']
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse('accounts:profile')
        )

        self.assertEqual(response.status_code, 200)


from django.core.cache import cache
from django.test import override_settings


class AuthenticationSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="auth-security-user",
            password="StrongPass123!",
        )

    def tearDown(self):
        cache.clear()

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)

    def test_logout_post_works(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(AUTH_LOGIN_ATTEMPTS=1, AUTH_LOGIN_WINDOW_SECONDS=60)
    def test_login_is_throttled(self):
        url = reverse("accounts:login")
        first = self.client.post(url, {"username": "wrong", "password": "wrong"})
        second = self.client.post(url, {"username": "wrong", "password": "wrong"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


import json
from django.core import mail
from django.test import override_settings


class AccountLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lifecycle-user",
            email="life@example.com",
            password="StrongPass123!",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_sends_email(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": self.user.email},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    def test_registration_requires_and_saves_unique_email(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new-email-user",
                "email": "NEW@Example.com",
                "password1": "AnotherStrongPass123!",
                "password2": "AnotherStrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username="new-email-user")
        self.assertEqual(created.email, "new@example.com")

    def test_export_requires_post_and_excludes_password(self):
        self.client.force_login(self.user)
        url = reverse("accounts:export_account_data")
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["account"]["username"], self.user.username)
        self.assertNotIn("password", response.content.decode().lower())

    def test_delete_requires_correct_confirmation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:delete_account"),
            {"confirmation": self.user.username, "password": "wrong"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_confirmed_delete_removes_user(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:delete_account"),
            {"confirmation": self.user.username, "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
