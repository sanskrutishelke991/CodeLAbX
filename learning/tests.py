from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Day, Roadmap


class LearningAuthorizationTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            username='roadmap-owner',
            password='StrongPass123!',
        )

        other_user = User.objects.create_user(
            username='other-learner',
            password='StrongPass123!',
        )

        self.roadmap = Roadmap.objects.create(
            user=owner,
            topic='ML',
            title='Private roadmap',
            total_days=1,
            daily_hours=1,
        )

        self.day = Day.objects.create(
            roadmap=self.roadmap,
            day_number=1,
            title='Private day',
            estimated_hours=1,
            order=1,
        )

        self.client.force_login(other_user)

    def test_other_user_cannot_view_roadmap(self):
        response = self.client.get(
            reverse(
                'learning:roadmap_detail',
                args=[self.roadmap.id],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_view_day(self):
        response = self.client.get(
            reverse(
                'learning:day_detail',
                args=[
                    self.roadmap.id,
                    self.day.day_number,
                ],
            )
        )

        self.assertEqual(response.status_code, 404)
