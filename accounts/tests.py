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
