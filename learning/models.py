from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Roadmap(models.Model):
    """Represents a complete learning path for a user."""
    
    TOPIC_CHOICES = [
        ('ML', 'Machine Learning'),
        ('DSA', 'Data Structures & Algorithms'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]
    
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roadmaps')
    topic = models.CharField(max_length=10, choices=TOPIC_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    total_days = models.PositiveIntegerField()
    daily_hours = models.DecimalField(max_digits=3, decimal_places=1)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['topic']),
            models.Index(fields=['status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_topic_display()})"
    
    @property
    def completed_days(self):
        return self.days.filter(is_completed=True).count()
    
    @property
    def progress_percentage(self):
        if self.total_days == 0:
            return 0
        return round((self.completed_days / self.total_days) * 100, 1)


class Day(models.Model):
    """Represents a single day in a roadmap."""
    
    roadmap = models.ForeignKey(Roadmap, on_delete=models.CASCADE, related_name='days')
    day_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    estimated_hours = models.DecimalField(max_digits=3, decimal_places=1)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField()
    ai_content = models.TextField(blank=True, null=True, help_text="AI generated theory content")
    ai_content_generated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['roadmap', 'day_number']
        indexes = [
            models.Index(fields=['roadmap']),
            models.Index(fields=['day_number']),
            models.Index(fields=['order']),
            models.Index(fields=['is_completed']),
        ]
    
    def __str__(self):
        return f"Day {self.day_number}: {self.title}"
    
    def mark_completed(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save()
