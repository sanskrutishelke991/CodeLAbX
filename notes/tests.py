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
