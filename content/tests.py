from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from progress.models import UserLevel, XPTransaction

from .models import Video, VideoCategory, UserVideoProgress


class VideoRewardIntegrityTests(TestCase):
    def test_video_reward_is_awarded_once(self):
        user = User.objects.create_user(username="video-xp-user", password="StrongPass123!")
        category = VideoCategory.objects.create(name="Python", slug="python")
        video = Video.objects.create(
            title="Safe Python",
            description="Test",
            youtube_id="abc123",
            category=category,
        )
        self.client.force_login(user)
        url = reverse("content:mark_watched", args=[video.id])
        first = self.client.post(url)
        second = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["xp_earned"], 10)
        self.assertEqual(second.json()["xp_earned"], 0)
        self.assertTrue(second.json()["already_watched"])
        self.assertEqual(UserLevel.objects.get(user=user).total_xp_earned, 10)
        self.assertEqual(XPTransaction.objects.filter(user=user).count(), 1)
        self.assertTrue(UserVideoProgress.objects.get(user=user, video=video).is_watched)


class ContentPaginationTests(TestCase):
    def test_library_is_paginated(self):
        user = User.objects.create_user(username="page-user", password="StrongPass123!")
        category = VideoCategory.objects.create(name="Paging", slug="paging")
        for index in range(13):
            Video.objects.create(
                title=f"Video {index}",
                description="Test",
                youtube_id=f"id-{index}",
                category=category,
            )
        self.client.force_login(user)
        response = self.client.get(reverse("content:library"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["videos"]), 12)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)

    def test_library_query_count_stays_bounded_with_many_videos(self):
        user = User.objects.create_user(
            username="library-query-user",
            password="StrongPass123!",
        )
        category = VideoCategory.objects.create(
            name="Query budget",
            slug="query-budget",
        )
        for index in range(30):
            Video.objects.create(
                title=f"Budget video {index}",
                description="Recorded test content",
                youtube_id=f"budget-{index}",
                category=category,
                is_featured=index < 6,
            )

        self.client.force_login(user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("content:library"))

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(queries),
            10,
            msg=f"Library exceeded query budget: {len(queries)}",
        )
