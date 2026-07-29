from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Challenge(models.Model):
    """Daily challenge for all users"""
    
    CHALLENGE_TYPES = [
        ('coding', 'Coding'),
        ('theory', 'Theory MCQ'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    date = models.DateField()
    challenge_type = models.CharField(max_length=20, choices=CHALLENGE_TYPES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    
    # For all challenges
    title = models.CharField(max_length=300)
    description = models.TextField()
    xp_reward = models.PositiveIntegerField(default=20)
    
    # For coding challenges
    starter_code = models.TextField(blank=True)
    example_input = models.TextField(blank=True)
    example_output = models.TextField(blank=True)
    hints = models.JSONField(default=list, blank=True)
    
    # For theory MCQ
    options = models.JSONField(default=list, blank=True)  # [{'text': 'Option A'}, ...]
    correct_option = models.PositiveIntegerField(default=0)
    explanation = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', 'challenge_type']
        unique_together = ['date', 'challenge_type']
    
    def __str__(self):
        return f"{self.date} - {self.get_challenge_type_display()}: {self.title[:50]}"
    
    @property
    def is_today(self):
        return self.date == timezone.now().date()


class UserChallenge(models.Model):
    """User's attempt on a challenge"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge_attempts')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='user_attempts')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    user_answer = models.TextField(blank=True)  # For coding
    selected_option = models.PositiveIntegerField(null=True, blank=True)  # For MCQ
    
    is_correct = models.BooleanField(default=False)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    xp_earned = models.PositiveIntegerField(default=0)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'challenge']
        ordering = ['-completed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.challenge.title[:30]}"


class ChallengeStreak(models.Model):
    """Track user's challenge streak (separate from learning streak)"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='challenge_streak')
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_challenge_date = models.DateField(null=True, blank=True)
    total_challenges_completed = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.user.username} - {self.current_streak} day challenge streak"
    
    def update_streak(self):
        """Update streak based on today's activity"""
        from datetime import timedelta
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        if self.last_challenge_date == today:
            return
        
        if self.last_challenge_date == yesterday:
            self.current_streak += 1
        else:
            self.current_streak = 1
        
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        self.last_challenge_date = today
        self.total_challenges_completed += 1
        self.save()