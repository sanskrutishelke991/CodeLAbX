from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Note


class NoteAuthorizationTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            username='note-owner',
            password='StrongPass123!',
        )

        other_user = User.objects.create_user(
            username='note-other',
            password='StrongPass123!',
        )

        self.note = Note.objects.create(
            user=owner,
            title='Private note',
            content='Only the owner may read this note.',
        )

        self.client.force_login(other_user)

    def test_other_user_cannot_edit_note(self):
        response = self.client.get(
            reverse(
                'notes:edit',
                args=[self.note.id],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_export_note(self):
        response = self.client.get(
            reverse(
                'notes:export',
                args=[self.note.id],
            )
        )

        self.assertEqual(response.status_code, 404)


import json

from .models import Bookmark


class BookmarkSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bookmark-security-user",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)
        self.url = reverse("notes:bookmark_add")

    def post(self, url):
        return self.client.post(
            self.url,
            data=json.dumps({"title": "Test", "url": url}),
            content_type="application/json",
        )

    def test_javascript_scheme_is_rejected(self):
        response = self.post("javascript:alert(1)")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_BOOKMARK_URL")

    def test_https_url_is_accepted(self):
        response = self.post("https://example.com/lesson")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Bookmark.objects.get(user=self.user).url, "https://example.com/lesson")

    def test_internal_relative_url_is_accepted(self):
        response = self.post("/learning/roadmaps/")
        self.assertEqual(response.status_code, 200)
