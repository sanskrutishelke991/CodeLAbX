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
