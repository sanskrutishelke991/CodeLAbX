from django.contrib.auth.models import User
from django.test import TestCase
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
