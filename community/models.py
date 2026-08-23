from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class StudyGroup(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_study_groups",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    max_members = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(max_members__gte=2) & Q(max_members__lte=100),
                name="study_group_member_limit_range",
            )
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.description = self.description.strip()
        if not self.name:
            raise ValidationError({"name": "Group name cannot be empty."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("moderator", "Moderator"),
        ("member", "Member"),
    ]
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_group_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_study_group_member",
            )
        ]
        indexes = [models.Index(fields=["user", "group"])]

    def clean(self):
        super().clean()
        if self.group_id and self.user_id:
            if self.user_id == self.group.owner_id and self.role != "owner":
                raise ValidationError({"role": "The group owner must keep the owner role."})
            if self.user_id != self.group.owner_id and self.role == "owner":
                raise ValidationError({"role": "Only the group owner can have the owner role."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.group_id}:{self.user_id}:{self.role}"


class GroupInvite(models.Model):
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_group_invites",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    max_uses = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(25)],
    )
    use_count = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(max_uses__gte=1) & Q(max_uses__lte=25),
                name="group_invite_max_uses_range",
            ),
            models.CheckConstraint(
                condition=Q(use_count__lte=F("max_uses")),
                name="group_invite_use_count_lte_max",
            ),
        ]

    def clean(self):
        super().clean()
        if self._state.adding and self.group_id and self.created_by_id and not GroupMembership.objects.filter(
            group=self.group,
            user_id=self.created_by_id,
            role__in={"owner", "moderator"},
        ).exists():
            raise ValidationError("Only group owners or moderators can create invites.")
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError({"expires_at": "Invite expiry must be in the future."})
        if self.use_count > self.max_uses:
            raise ValidationError({"use_count": "Invite usage exceeds its limit."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_usable(self):
        return bool(
            self.is_active
            and self.use_count < self.max_uses
            and self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"{self.group_id}:{self.token}"


class GroupRoadmapShare(models.Model):
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name="roadmap_shares",
    )
    roadmap = models.ForeignKey(
        "learning.Roadmap",
        on_delete=models.CASCADE,
        related_name="group_shares",
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_group_roadmaps",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "roadmap"],
                name="unique_roadmap_share_per_group",
            )
        ]

    def clean(self):
        super().clean()
        if self._state.adding and self.roadmap_id and self.shared_by_id != self.roadmap.user_id:
            raise ValidationError(
                {"shared_by": "Only the roadmap owner can share it with a group."}
            )
        if self._state.adding and self.group_id and self.shared_by_id and not GroupMembership.objects.filter(
            group=self.group,
            user_id=self.shared_by_id,
        ).exists():
            raise ValidationError(
                {"shared_by": "The roadmap owner must be a member of the group."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DiscussionThread(models.Model):
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name="threads",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_threads",
    )
    title = models.CharField(max_length=180)
    body = models.TextField(max_length=3000)
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_community_threads",
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-updated_at"]
        indexes = [models.Index(fields=["group", "is_hidden", "updated_at"])]

    def clean(self):
        super().clean()
        self.title = self.title.strip()
        self.body = self.body.strip()
        if not self.title or not self.body:
            raise ValidationError("Thread title and body are required.")
        if self._state.adding and self.group_id and self.author_id and not GroupMembership.objects.filter(
            group=self.group,
            user_id=self.author_id,
        ).exists():
            raise ValidationError("Thread authors must be active group members.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DiscussionPost(models.Model):
    thread = models.ForeignKey(
        DiscussionThread,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_posts",
    )
    body = models.TextField(max_length=2500, blank=True)
    is_deleted = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_community_posts",
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["thread", "is_hidden", "created_at"])]

    def clean(self):
        super().clean()
        self.body = self.body.strip()
        if not self.body and not self.is_deleted:
            raise ValidationError({"body": "Post body cannot be empty."})
        if self._state.adding and self.thread_id and self.author_id and not GroupMembership.objects.filter(
            group=self.thread.group,
            user_id=self.author_id,
        ).exists():
            raise ValidationError("Post authors must be active group members.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DayComment(models.Model):
    day = models.ForeignKey(
        "learning.Day",
        on_delete=models.CASCADE,
        related_name="community_comments",
    )
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="day_comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="roadmap_day_comments",
    )
    body = models.TextField(max_length=1200, blank=True)
    is_deleted = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_day_comments",
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["day", "group", "created_at"])]

    def clean(self):
        super().clean()
        self.body = self.body.strip()
        if not self.body and not self.is_deleted:
            raise ValidationError({"body": "Comment cannot be empty."})
        if self._state.adding and self.day_id and self.author_id:
            if self.group_id is None and self.author_id != self.day.roadmap.user_id:
                raise ValidationError(
                    "Personal day comments belong only to the roadmap owner."
                )
            if self.group_id is not None:
                if not GroupMembership.objects.filter(
                    group=self.group,
                    user_id=self.author_id,
                ).exists():
                    raise ValidationError("Group comments require active membership.")
                if not GroupRoadmapShare.objects.filter(
                    group=self.group,
                    roadmap=self.day.roadmap,
                ).exists():
                    raise ValidationError("The roadmap is not shared with this group.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_blocks_created",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_community_user_block",
            ),
            models.CheckConstraint(
                condition=~Q(blocker=F("blocked")),
                name="community_user_cannot_block_self",
            ),
        ]

    def clean(self):
        super().clean()
        if self.blocker_id == self.blocked_id:
            raise ValidationError("You cannot block yourself.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CommunityReport(models.Model):
    TARGET_CHOICES = [
        ("thread", "Discussion thread"),
        ("post", "Discussion post"),
        ("day_comment", "Roadmap day comment"),
    ]
    REASON_CHOICES = [
        ("spam", "Spam"),
        ("harassment", "Harassment or bullying"),
        ("privacy", "Private information"),
        ("unsafe", "Unsafe content"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("resolved", "Resolved"),
        ("dismissed", "Dismissed"),
    ]

    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_reports",
    )
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_id = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    details = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_community_reports",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "target_type", "target_id"],
                name="unique_community_report_per_target",
            )
        ]
        indexes = [models.Index(fields=["group", "status", "created_at"])]

    def clean(self):
        super().clean()
        self.details = self.details.strip()
        if self._state.adding and self.group_id and self.reporter_id and not GroupMembership.objects.filter(
            group=self.group,
            user_id=self.reporter_id,
        ).exists():
            raise ValidationError("Only group members can report group content.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
