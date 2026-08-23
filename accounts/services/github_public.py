"""Token-free synchronization of public GitHub profile/repository metadata."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import (
    GITHUB_USERNAME_RE,
    GitHubConnection,
    GitHubRepository,
)

logger = logging.getLogger(__name__)
GITHUB_API_ORIGIN = "https://api.github.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class GitHubPublicAPIError(Exception):
    def __init__(self, code, public_message):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


class _FixedOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        parsed = urlparse(new_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "api.github.com":
            raise GitHubPublicAPIError(
                "github_redirect_blocked",
                "GitHub returned an unsupported redirect.",
            )
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            new_url,
        )


@dataclass(frozen=True)
class GitHubSyncResult:
    connection: GitHubConnection
    repository_count: int


def _safe_github_url(value, *, expected_prefix="/"):
    if not isinstance(value, str) or len(value) > 500:
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            "GitHub returned invalid public metadata.",
        )
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "github.com"
        or parsed.path.rstrip("/") != expected_prefix.rstrip("/")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            "GitHub returned an unsupported public URL.",
        )
    return value


def _bounded_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            f"GitHub returned an invalid {field} value.",
        )
    return value


def _request_json(path):
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise ValueError("GitHub API path must be relative to the fixed origin.")
    request = urllib.request.Request(
        GITHUB_API_ORIGIN + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CodeLabX-public-portfolio",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_FixedOriginRedirectHandler())
    try:
        with opener.open(
            request,
            timeout=settings.GITHUB_API_TIMEOUT_SECONDS,
        ) as response:
            content_type = response.headers.get_content_type()
            if content_type != "application/json":
                raise GitHubPublicAPIError(
                    "invalid_provider_content_type",
                    "GitHub returned an unsupported response type.",
                )
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise GitHubPublicAPIError(
                "github_user_not_found",
                "That public GitHub username was not found.",
            ) from exc
        if exc.code in {403, 429}:
            raise GitHubPublicAPIError(
                "github_rate_limited",
                "GitHub temporarily refused the public request. Try again later.",
            ) from exc
        raise GitHubPublicAPIError(
            "github_unavailable",
            "GitHub public data is temporarily unavailable.",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitHubPublicAPIError(
            "github_unavailable",
            "GitHub public data is temporarily unavailable.",
        ) from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise GitHubPublicAPIError(
            "github_response_too_large",
            "GitHub returned more public data than CodeLabX accepts.",
        )
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            "GitHub returned invalid public metadata.",
        ) from exc


def _profile_snapshot(payload, requested_username):
    if not isinstance(payload, dict):
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            "GitHub returned invalid public profile metadata.",
        )
    login = payload.get("login")
    github_id = payload.get("id")
    if (
        not isinstance(login, str)
        or login.casefold() != requested_username.casefold()
    ):
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            "GitHub returned a different public profile.",
        )
    github_id = _bounded_int(github_id, "user ID")
    profile_url = _safe_github_url(
        payload.get("html_url"),
        expected_prefix=f"/{login}",
    )
    name = payload.get("name") or ""
    bio = payload.get("bio") or ""
    if not isinstance(name, str) or not isinstance(bio, str):
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            "GitHub returned invalid profile text.",
        )
    return {
        "username": login,
        "github_user_id": github_id,
        "profile_url": profile_url,
        "display_name": name.strip()[:100],
        "bio": bio.strip()[:300],
        "public_repos": _bounded_int(payload.get("public_repos", 0), "repository count"),
        "followers": _bounded_int(payload.get("followers", 0), "follower count"),
    }


def _repository_snapshots(payload, login, fetched_at):
    if not isinstance(payload, list):
        raise GitHubPublicAPIError(
            "invalid_provider_data",
            "GitHub returned invalid repository metadata.",
        )
    repositories = []
    for item in payload[:100]:
        if not isinstance(item, dict):
            continue
        github_id = item.get("id")
        name = item.get("name")
        full_name = item.get("full_name")
        if (
            isinstance(github_id, bool)
            or not isinstance(github_id, int)
            or github_id < 1
            or not isinstance(name, str)
            or not 1 <= len(name) <= 100
            or not isinstance(full_name, str)
            or not 1 <= len(full_name) <= 200
            or not full_name.casefold().startswith(login.casefold() + "/")
        ):
            continue
        try:
            html_url = _safe_github_url(
                item.get("html_url"),
                expected_prefix=f"/{full_name}",
            )
            stars = _bounded_int(item.get("stargazers_count", 0), "star count")
            forks = _bounded_int(item.get("forks_count", 0), "fork count")
        except GitHubPublicAPIError:
            continue
        description = item.get("description") or ""
        language = item.get("language") or ""
        is_fork = item.get("fork", False)
        if (
            not isinstance(description, str)
            or not isinstance(language, str)
            or not isinstance(is_fork, bool)
        ):
            continue
        pushed_at = parse_datetime(item.get("pushed_at") or "")
        repositories.append(
            GitHubRepository(
                github_id=github_id,
                name=name,
                full_name=full_name,
                html_url=html_url,
                description=description.strip()[:500],
                language=language.strip()[:100],
                stargazers_count=stars,
                forks_count=forks,
                is_fork=is_fork,
                pushed_at=pushed_at,
                fetched_at=fetched_at,
            )
        )
    repositories.sort(
        key=lambda repo: (
            repo.pushed_at or datetime.min.replace(tzinfo=datetime_timezone.utc),
            repo.name.casefold(),
        ),
        reverse=True,
    )
    return repositories[: settings.GITHUB_MAX_REPOSITORIES]


def record_sync_failure(user, username, error_code):
    """Store only a generic provider state; never provider response details."""
    connection, _ = GitHubConnection.objects.get_or_create(
        user=user,
        defaults={"username": username},
    )
    if connection.username.casefold() != username.casefold() and connection.status == "synced":
        return connection
    connection.username = username
    connection.status = "error"
    connection.last_error_code = error_code[:60]
    connection.save()
    return connection


@transaction.atomic
def _store_snapshot(user, profile, repositories, fetched_at):
    user.__class__.objects.select_for_update().get(pk=user.pk)
    connection = (
        GitHubConnection.objects.select_for_update().filter(user=user).first()
    )
    if connection is None:
        connection = GitHubConnection(user=user, username=profile["username"])
    for field, value in profile.items():
        setattr(connection, field, value)
    connection.status = "synced"
    connection.last_error_code = ""
    connection.fetched_at = fetched_at
    connection.save()
    connection.repositories.all().delete()
    for repository in repositories:
        repository.connection = connection
    GitHubRepository.objects.bulk_create(repositories)
    return GitHubSyncResult(
        connection=connection,
        repository_count=len(repositories),
    )


def sync_public_github(user, username):
    """Fetch only public data from fixed GitHub API endpoints, without OAuth."""
    if not settings.GITHUB_PUBLIC_INTEGRATION_ENABLED:
        raise GitHubPublicAPIError(
            "github_integration_disabled",
            "GitHub public portfolio integration is disabled.",
        )
    username = str(username).strip()
    if not GITHUB_USERNAME_RE.fullmatch(username):
        raise ValidationError("Enter a valid public GitHub username.")
    quoted = urllib.parse.quote(username, safe="")
    profile_payload = _request_json(f"/users/{quoted}")
    repositories_payload = _request_json(
        f"/users/{quoted}/repos?per_page=100&sort=updated&type=owner"
    )
    fetched_at = timezone.now()
    profile = _profile_snapshot(profile_payload, username)
    repositories = _repository_snapshots(
        repositories_payload,
        profile["username"],
        fetched_at,
    )
    return _store_snapshot(user, profile, repositories, fetched_at)
