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


class NoteInputAndLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="note-input-user",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)

    def test_create_normalizes_and_deduplicates_tags(self):
        response = self.client.post(
            reverse("notes:create"),
            {
                "title": "Validated note",
                "content": "Content",
                "color": "blue",
                "tags": "Python, python, Django,  Django ",
            },
        )
        self.assertEqual(response.status_code, 302)
        note = Note.objects.get(user=self.user)
        self.assertEqual(note.tags, ["Python", "Django"])
        self.assertEqual(note.color, "blue")

    def test_invalid_color_and_oversized_title_are_rejected(self):
        invalid_payloads = [
            {
                "title": "Invalid color",
                "content": "Content",
                "color": "transparent",
            },
            {
                "title": "x" * 201,
                "content": "Content",
                "color": "purple",
            },
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(reverse("notes:create"), payload)
                self.assertEqual(response.status_code, 302)
        self.assertFalse(Note.objects.filter(user=self.user).exists())

    def test_invalid_edit_does_not_destroy_existing_values(self):
        note = Note.objects.create(
            user=self.user,
            title="Original",
            content="Original content",
            color="green",
        )
        response = self.client.post(
            reverse("notes:edit", args=[note.id]),
            {"title": "", "content": "Changed", "color": "red"},
        )
        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertEqual(note.title, "Original")
        self.assertEqual(note.content, "Original content")
        self.assertEqual(note.color, "green")

    def test_export_uses_safe_fixed_filename_and_no_store(self):
        note = Note.objects.create(
            user=self.user,
            title='Unsafe " filename',
            content="Private content",
        )
        response = self.client.get(reverse("notes:export", args=[note.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="codelabx-note-{note.id}.txt"',
        )
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertContains(response, "Private content")

    def test_pin_and_delete_require_post_and_update_state(self):
        note = Note.objects.create(
            user=self.user,
            title="Lifecycle",
            content="Content",
        )
        pin_url = reverse("notes:pin_toggle", args=[note.id])
        delete_url = reverse("notes:delete", args=[note.id])
        self.assertEqual(self.client.get(pin_url).status_code, 405)
        self.assertTrue(self.client.post(pin_url).json()["is_pinned"])
        note.refresh_from_db()
        self.assertTrue(note.is_pinned)
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        self.assertEqual(self.client.post(delete_url).status_code, 302)
        self.assertFalse(Note.objects.filter(id=note.id).exists())
