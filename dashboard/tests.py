from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from challenges.models import Challenge


class RouteSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='smoke-user',
            password='StrongPass123!',
        )

    def test_public_pages_render(self):
        routes = [
            'landing',
            'accounts:login',
            'accounts:register',
        ]

        for name in routes:
            with self.subTest(name=name):
                response = self.client.get(
                    reverse(name)
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    def test_authenticated_pages_render(self):
        self.client.force_login(self.user)

        routes = [
            'dashboard:home',
            'accounts:profile',
            'accounts:profile_edit',
            'accounts:settings',
            'learning:roadmaps',
            'learning:roadmap_create',
            'content:library',
            'content:my_videos',
            'practice:task_list',
            'practice:examiner',
            'assessments:quiz_list',
            'assessments:create',
            'ai_tools:home',
            'ai_tools:image_analyzer',
            'ai_tools:image_history',
            'progress:achievements',
            'progress:leaderboard',
            'progress:analytics',
            'notes:list',
            'notes:create',
            'notes:bookmarks',
        ]

        for name in routes:
            with self.subTest(name=name):
                response = self.client.get(
                    reverse(name)
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    @patch(
        'challenges.views.'
        'get_or_create_today_challenges'
    )
    def test_challenge_dashboard_without_ai_call(
        self,
        generator,
    ):
        generator.return_value = (
            Challenge.objects.none()
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse('challenges:dashboard')
        )

        self.assertEqual(response.status_code, 200)


from django.contrib import admin
from accounts.models import UserProfile
from assessments.models import Test
from challenges.models import Challenge
from content.models import Video
from learning.models import Roadmap
from notes.models import Note
from practice.models import CodeReview
from progress.models import XPTransaction


class AdminRegistrationTests(TestCase):
    def test_operational_models_are_registered(self):
        for model in [
            UserProfile,
            Test,
            Challenge,
            Video,
            Roadmap,
            Note,
            CodeReview,
            XPTransaction,
        ]:
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)
