import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from progress.models import UserLevel, XPTransaction

from .models import Challenge, UserChallenge


@override_settings(AI_FEATURES_ENABLED=False)
class ChallengeRewardIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="challenge-xp-user", password="StrongPass123!")
        self.client.force_login(self.user)

    def test_theory_challenge_reward_is_awarded_once(self):
        challenge = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="theory",
            difficulty="easy",
            title="Question",
            description="Choose zero",
            options=[{"text": "A"}, {"text": "B"}],
            correct_option=0,
            xp_reward=20,
        )
        url = reverse("challenges:submit", args=[challenge.id])
        payload = json.dumps({"selected_option": 0, "time_taken": 10})
        first = self.client.post(url, data=payload, content_type="application/json")
        second = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["xp_earned"], 20)
        self.assertEqual(second.json()["xp_earned"], 0)
        self.assertTrue(second.json()["already_completed"])
        self.assertEqual(UserLevel.objects.get(user=self.user).total_xp_earned, 20)
        self.assertEqual(XPTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserChallenge.objects.filter(user=self.user).count(), 1)

    def test_coding_ai_failure_does_not_grant_correctness(self):
        challenge = Challenge.objects.create(
            date=timezone.localdate(),
            challenge_type="coding",
            difficulty="easy",
            title="Code",
            description="Write code",
            xp_reward=30,
        )
        response = self.client.post(
            reverse("challenges:submit", args=[challenge.id]),
            data=json.dumps({"code": "print(1)", "time_taken": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_correct"])
        self.assertEqual(response.json()["xp_earned"], 9)
