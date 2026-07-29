from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Test(models.Model):
    """Represents a quiz/test created by a user."""
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests')
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    num_questions = models.PositiveIntegerField(default=10)
    time_limit_minutes = models.PositiveIntegerField(default=10)
    questions = models.JSONField(default=list)  # Stores generated questions
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    score = models.PositiveIntegerField(null=True, blank=True)
    total_marks = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['topic']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_difficulty_display()})"
    
    @property
    def percentage(self):
        if self.total_marks == 0:
            return 0
        return round((self.score / self.total_marks) * 100, 1)
    
    @property
    def grade(self):
        percentage = self.percentage
        if percentage >= 97:
            return 'A+'
        elif percentage >= 93:
            return 'A'
        elif percentage >= 90:
            return 'A-'
        elif percentage >= 87:
            return 'B+'
        elif percentage >= 83:
            return 'B'
        elif percentage >= 80:
            return 'B-'
        elif percentage >= 77:
            return 'C+'
        elif percentage >= 73:
            return 'C'
        elif percentage >= 70:
            return 'C-'
        elif percentage >= 67:
            return 'D+'
        elif percentage >= 63:
            return 'D'
        elif percentage >= 60:
            return 'D-'
        else:
            return 'F'


class TestAttempt(models.Model):
    """Represents a user's attempt at a test."""
    
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_attempts')
    answers = models.JSONField(default=dict)  # Stores user's answers {question_index: selected_option}
    score = models.PositiveIntegerField(null=True, blank=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['test']),
            models.Index(fields=['user']),
            models.Index(fields=['completed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s attempt at {self.test.title}"
    
    @property
    def percentage(self):
        if self.test.total_marks == 0:
            return 0
        return round((self.score / self.test.total_marks) * 100, 1)
