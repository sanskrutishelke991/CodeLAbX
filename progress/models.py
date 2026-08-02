from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class DailyActivity(models.Model):
    """Track user's daily learning activity"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_activities')
    date = models.DateField()
    minutes_studied = models.PositiveIntegerField(default=0)
    days_completed = models.PositiveIntegerField(default=0)
    topics_studied = models.TextField(blank=True)  # JSON list of topics
    
    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.date}"
    
    @property
    def activity_level(self):
        """Return 0-4 based on minutes studied"""
        if self.minutes_studied == 0:
            return 0
        elif self.minutes_studied < 30:
            return 1
        elif self.minutes_studied < 60:
            return 2
        elif self.minutes_studied < 120:
            return 3
        else:
            return 4


class UserStreak(models.Model):
    """Track user's learning streak"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    total_days_active = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.user.username} - {self.current_streak} days"
    
    def update_streak(self):
        """Update streak based on today's activity"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        if self.last_activity_date == today:
            # Already active today
            return
        
        if self.last_activity_date == yesterday:
            # Continuing streak
            self.current_streak += 1
        else:
            # Streak broken, restart
            self.current_streak = 1
        
        # Update longest streak
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        self.last_activity_date = today
        self.total_days_active += 1
        self.save()


class Badge(models.Model):
    """Represents an achievement badge that can be earned."""
    
    CATEGORY_CHOICES = [
        ('streak', 'Streak'),
        ('learning', 'Learning'),
        ('practice', 'Practice'),
        ('test', 'Test'),
        ('special', 'Special'),
    ]
    
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50)  # Emoji or icon class
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    rarity = models.CharField(max_length=20, choices=RARITY_CHOICES, default='common')
    xp_reward = models.PositiveIntegerField(default=10)
    requirement_type = models.CharField(max_length=50)  # e.g., 'streak_days', 'topics_completed'
    requirement_value = models.PositiveIntegerField()  # e.g., 7 for 7-day streak
    color = models.CharField(max_length=7, default='#a0a0a0')  # Hex color
    
    class Meta:
        ordering = ['rarity', 'category', 'name']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['rarity']),
        ]
    
    def __str__(self):
        return f"{self.icon} {self.name} ({self.get_rarity_display()})"


class UserBadge(models.Model):
    """Represents a badge earned by a user."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='earned_by')
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-earned_at']
        unique_together = ['user', 'badge']
        indexes = [
            models.Index(fields=['user', 'earned_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"


class UserLevel(models.Model):
    """Tracks user's XP and level progression."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='level')
    current_xp = models.PositiveIntegerField(default=0)
    current_level = models.PositiveIntegerField(default=1)
    total_xp_earned = models.PositiveIntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['current_level']),
            models.Index(fields=['total_xp_earned']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Level {self.current_level}"
    
    def add_xp(self, amount):
        """Add XP and check for level up."""
        self.current_xp += amount
        self.total_xp_earned += amount
        
        xp_needed = self.xp_for_next_level()
        while self.current_xp >= xp_needed:
            self.current_xp -= xp_needed
            self.current_level += 1
            xp_needed = self.xp_for_next_level()
        
        self.save()
        return self.current_level
    
    def xp_for_next_level(self):
        """Calculate XP needed for next level."""
        return self.current_level * 100
    
    def level_progress_percentage(self):
        """Percentage progress to next level."""
        xp_needed = self.xp_for_next_level()
        if xp_needed == 0:
            return 0
        return round((self.current_xp / xp_needed) * 100, 1)

class XPTransaction(models.Model):
    """Immutable record of one idempotent XP award."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="xp_transactions",
    )
    amount = models.PositiveIntegerField()
    event_type = models.CharField(max_length=50)
    reason = models.CharField(max_length=200)
    idempotency_key = models.CharField(max_length=255)
    source_object_type = models.CharField(max_length=50, blank=True)
    source_object_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                name="unique_user_xp_idempotency_key",
            )
        ]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self):
        return f"{self.user.username}: +{self.amount} XP ({self.event_type})"
