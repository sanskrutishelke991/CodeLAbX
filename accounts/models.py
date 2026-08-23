from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, validate_email
from django.db import models
from django.contrib.auth.models import User
import os


def user_avatar_path(instance, filename):
    """Generate path for user avatar"""
    ext = filename.split('.')[-1]
    return f'avatars/user_{instance.user.id}.{ext}'


class UserProfile(models.Model):
    """Extended user profile with social links and personal info"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to=user_avatar_path, blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    # Social Links
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    
    # Learning Info
    skills = models.JSONField(default=list, blank=True)
    learning_goals = models.TextField(blank=True)
    
    # Settings
    is_public = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def avatar_url(self):
        """Return avatar URL or None"""
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None
    
    @property
    def initials(self):
        """Return user initials for avatar fallback"""
        return self.user.username[0].upper()
    
    def get_skill_color(self, skill):
        """Get color for a skill tag"""
        colors = {
            'python': '#4B8BBE',
            'javascript': '#F0DB4F',
            'js': '#F0DB4F',
            'react': '#61DAFB',
            'django': '#092E20',
            'ai': '#FF6B6B',
            'ml': '#FF6B6B',
            'machine learning': '#FF6B6B',
            'html': '#E34F26',
            'css': '#1572B6',
            'java': '#ED751E',
            'c++': '#00599C',
            'sql': '#4479A1',
            'git': '#F05032',
            'docker': '#2496ED',
            'aws': '#FF9900',
        }
        default_colors = ['#6C63FF', '#00D4AA', '#FF6B6B', '#f59e0b', '#a855f7', '#4a90e2']
        skill_lower = skill.lower().strip()
        
        if skill_lower in colors:
            return colors[skill_lower]
        
        # Deterministic color based on skill name
        return default_colors[hash(skill_lower) % len(default_colors)]

class EmailPreference(models.Model):
    WEEKDAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="email_preference",
    )
    weekly_report_enabled = models.BooleanField(default=False)
    report_weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
    )
    include_activity = models.BooleanField(default=True)
    include_skill_progress = models.BooleanField(default=True)
    include_next_steps = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(report_weekday__gte=0)
                & models.Q(report_weekday__lte=6),
                name="email_report_weekday_range",
            )
        ]

    def clean(self):
        super().clean()
        email = (self.user.email or "").strip()
        if self.weekly_report_enabled:
            try:
                validate_email(email)
            except ValidationError as exc:
                raise ValidationError(
                    {
                        "weekly_report_enabled": (
                            "A valid account email is required before weekly "
                            "reports can be enabled."
                        )
                    }
                ) from exc
        if self.weekly_report_enabled and not any(
            (
                self.include_activity,
                self.include_skill_progress,
                self.include_next_steps,
            )
        ):
            raise ValidationError(
                "Select at least one weekly report section."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}: weekly reports {'on' if self.weekly_report_enabled else 'off'}"


class WeeklyReportDelivery(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="weekly_report_deliveries",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    subject = models.CharField(max_length=200, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "period_start", "period_end"],
                name="unique_user_weekly_report_period",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status", "period_end"]),
        ]

    def clean(self):
        super().clean()
        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                raise ValidationError(
                    {"period_end": "Report period end must follow its start."}
                )
            if (self.period_end - self.period_start).days != 6:
                raise ValidationError(
                    {"period_end": "A weekly report must cover exactly seven days."}
                )
        if self.status == "sent" and (
            self.sent_at is None or len(self.content_hash) != 64
        ):
            raise ValidationError(
                "A sent report requires its sent time and content hash."
            )
        if self.status == "failed" and not self.error_code:
            raise ValidationError(
                {"error_code": "A failed report requires a generic error code."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id}:{self.period_start}:{self.status}"
