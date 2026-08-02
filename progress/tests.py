from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Badge, UserLevel


class ProgressPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='visible-learner',
            password='StrongPass123!',
        )

        UserLevel.objects.create(
            user=self.user,
            total_xp_earned=250,
        )

        self.client.force_login(self.user)

        self.badge = Badge.objects.create(
            name='Code Route Test',
            description=(
                'Used to verify the badge detail route.'
            ),
            icon='T',
            category='practice',
            rarity='common',
            xp_reward=10,
            requirement_type='code_reviews',
            requirement_value=1,
        )

    def test_locked_code_badge_detail_renders(self):
        response = self.client.get(
            reverse(
                'progress:badge_detail',
                args=[self.badge.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.badge.name)
        self.assertContains(response, '0%')

    def test_missing_badge_returns_404(self):
        response = self.client.get(
            reverse(
                'progress:badge_detail',
                args=[999999],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_leaderboard_displays_public_user(self):
        response = self.client.get(
            reverse('progress:leaderboard')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            self.user.username,
        )

    def test_leaderboard_hides_private_profile(self):
        private_user = User.objects.create_user(
            username='private-learner',
            password='StrongPass123!',
        )

        private_user.profile.is_public = False
        private_user.profile.save(
            update_fields=['is_public']
        )

        UserLevel.objects.create(
            user=private_user,
            total_xp_earned=9999,
        )

        response = self.client.get(
            reverse('progress:leaderboard')
        )

        self.assertNotContains(
            response,
            private_user.username,
        )
