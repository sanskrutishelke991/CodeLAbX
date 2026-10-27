from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import GitHubConnection, GitHubRepository
from .services.github_public import (
    GitHubPublicAPIError,
    _FixedOriginRedirectHandler,
    _request_json,
    record_sync_failure,
    sync_public_github,
)


PROFILE = {
    "login": "octo-learner",
    "id": 12345,
    "html_url": "https://github.com/octo-learner",
    "name": "Octo Learner",
    "bio": "Public profile bio",
    "public_repos": 2,
    "followers": 7,
}
REPOSITORIES = [
    {
        "id": 101,
        "name": "learning-project",
        "full_name": "octo-learner/learning-project",
        "html_url": "https://github.com/octo-learner/learning-project",
        "description": "A public learning project",
        "language": "Python",
        "stargazers_count": 4,
        "forks_count": 1,
        "fork": False,
        "pushed_at": "2026-08-20T10:00:00Z",
    },
    {
        "id": 102,
        "name": "web-project",
        "full_name": "octo-learner/web-project",
        "html_url": "https://github.com/octo-learner/web-project",
        "description": "Public web project",
        "language": "JavaScript",
        "stargazers_count": 2,
        "forks_count": 0,
        "fork": False,
        "pushed_at": "2026-08-21T10:00:00Z",
    },
]


@override_settings(
    GITHUB_PUBLIC_INTEGRATION_ENABLED=True,
    GITHUB_MAX_REPOSITORIES=30,
    GITHUB_API_TIMEOUT_SECONDS=8,
)
class GitHubPublicServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="github-service-user",
            password="StrongPass123!",
        )

    @patch("accounts.services.github_public._request_json")
    def test_sync_stores_only_bounded_public_snapshot_without_token(self, request_json):
        request_json.side_effect = [PROFILE, REPOSITORIES]
        result = sync_public_github(self.user, "octo-learner")
        self.assertEqual(result.repository_count, 2)
        connection = result.connection
        self.assertEqual(connection.status, "synced")
        self.assertEqual(connection.github_user_id, 12345)
        self.assertEqual(connection.profile_url, PROFILE["html_url"])
        self.assertEqual(connection.repositories.count(), 2)
        self.assertEqual(
            connection.repositories.get(github_id=101).language,
            "Python",
        )
        self.assertFalse(hasattr(connection, "access_token"))
        self.assertFalse(hasattr(connection, "oauth_token"))
        self.assertEqual(
            request_json.call_args_list[0].args[0],
            "/users/octo-learner",
        )
        self.assertIn("/users/octo-learner/repos?", request_json.call_args_list[1].args[0])

    @patch("accounts.services.github_public._request_json")
    def test_refresh_replaces_stale_rows_and_skips_malformed_provider_items(self, request_json):
        request_json.side_effect = [PROFILE, REPOSITORIES]
        first = sync_public_github(self.user, "octo-learner")
        malformed = {
            **REPOSITORIES[0],
            "id": 999,
            "html_url": "https://evil.example/repository",
        }
        updated = [{**REPOSITORIES[0], "stargazers_count": 9}, malformed]
        request_json.side_effect = [PROFILE, updated]
        second = sync_public_github(self.user, "octo-learner")
        self.assertEqual(first.connection.id, second.connection.id)
        self.assertEqual(second.repository_count, 1)
        self.assertEqual(
            second.connection.repositories.get().stargazers_count,
            9,
        )
        self.assertFalse(
            GitHubRepository.objects.filter(github_id=102).exists()
        )
        self.assertFalse(
            GitHubRepository.objects.filter(github_id=999).exists()
        )

    def test_fixed_origin_helper_rejects_absolute_or_oversized_paths(self):
        with self.assertRaises(ValueError):
            _request_json("https://evil.example/users/test")
        with self.assertRaises(ValueError):
            _request_json("//evil.example/users/test")
        with self.assertRaises(GitHubPublicAPIError):
            _FixedOriginRedirectHandler().redirect_request(
                None,
                None,
                302,
                "Found",
                {},
                "https://evil.example/redirect",
            )

    def test_failure_state_uses_generic_code_only(self):
        connection = record_sync_failure(
            self.user,
            "octo-learner",
            "github_unavailable",
        )
        self.assertEqual(connection.status, "error")
        self.assertEqual(connection.last_error_code, "github_unavailable")
        self.assertNotIn("http", connection.last_error_code)

    def test_model_rejects_invalid_username_and_unproven_synced_state(self):
        with self.assertRaises(ValidationError):
            GitHubConnection.objects.create(
                user=self.user,
                username="-invalid--name-",
            )
        connection = GitHubConnection(
            user=self.user,
            username="valid-name",
            status="synced",
        )
        with self.assertRaises(ValidationError):
            connection.save()

    def test_github_models_are_registered_in_admin(self):
        self.assertIn(GitHubConnection, admin.site._registry)
        self.assertIn(GitHubRepository, admin.site._registry)


@override_settings(
    GITHUB_PUBLIC_INTEGRATION_ENABLED=True,
    GITHUB_REFRESH_ATTEMPTS=10,
    GITHUB_REFRESH_WINDOW_SECONDS=3600,
)
class GitHubPublicViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="github-view-user",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="github-view-other",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    @patch("accounts.views.sync_public_github")
    def test_connect_refresh_disconnect_are_post_only_and_owner_scoped(self, sync):
        connection = GitHubConnection.objects.create(
            user=self.user,
            username="octo-learner",
        )
        sync.return_value = type(
            "Result",
            (),
            {"repository_count": 2, "connection": connection},
        )()
        connect_url = reverse("accounts:github_connect")
        refresh_url = reverse("accounts:github_refresh")
        disconnect_url = reverse("accounts:github_disconnect")
        for url in (connect_url, refresh_url, disconnect_url):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(
            connect_url,
            {"username": "octo-learner"},
        )
        self.assertRedirects(response, reverse("accounts:github_portfolio"))
        sync.assert_called_with(self.user, "octo-learner")
        self.client.post(refresh_url)
        self.assertEqual(sync.call_count, 2)

        other_connection = GitHubConnection.objects.create(
            user=self.other,
            username="other-public",
        )
        self.client.post(disconnect_url)
        self.assertFalse(GitHubConnection.objects.filter(user=self.user).exists())
        self.assertTrue(
            GitHubConnection.objects.filter(id=other_connection.id).exists()
        )

    @patch("accounts.views.sync_public_github")
    def test_provider_error_is_generic_and_does_not_leak_detail(self, sync):
        sync.side_effect = GitHubPublicAPIError(
            "github_unavailable",
            "GitHub public data is temporarily unavailable.",
        )
        response = self.client.post(
            reverse("accounts:github_connect"),
            {"username": "octo-learner"},
            follow=True,
        )
        self.assertContains(response, "temporarily unavailable")
        self.assertNotContains(response, "SECRET")
        connection = GitHubConnection.objects.get(user=self.user)
        self.assertEqual(connection.last_error_code, "github_unavailable")

    def test_portfolio_page_states_public_only_and_not_verified(self):
        connection = GitHubConnection.objects.create(
            user=self.user,
            username="octo-learner",
            github_user_id=12345,
            profile_url="https://github.com/octo-learner",
            status="synced",
            fetched_at=timezone.now(),
        )
        GitHubRepository.objects.create(
            connection=connection,
            github_id=101,
            name="safe-repository",
            full_name="octo-learner/safe-repository",
            html_url="https://github.com/octo-learner/safe-repository",
            description="<script>not executable</script>",
            language="Python",
            fetched_at=connection.fetched_at,
        )
        response = self.client.get(reverse("accounts:github_portfolio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public metadata only")
        self.assertContains(response, "Not identity verification")
        self.assertContains(response, "No access token is stored")
        self.assertContains(response, "&lt;script&gt;not executable&lt;/script&gt;")
        self.assertNotContains(response, "<script>not executable</script>")

    def test_account_export_contains_public_cache_but_no_error_or_token(self):
        GitHubConnection.objects.create(
            user=self.user,
            username="octo-learner",
        )
        response = self.client.post(reverse("accounts:export_account_data"))
        data = json.loads(response.content)
        self.assertEqual(
            data["github_public_connection"]["username"],
            "octo-learner",
        )
        serialized = response.content.decode().lower()
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("last_error_code", serialized)
