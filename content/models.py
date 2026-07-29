from django.db import models
from django.contrib.auth.models import User


class VideoCategory(models.Model):
    """Categories for videos"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10, default='📺')
    color = models.CharField(max_length=20, default='#6C63FF')
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Video Categories'
    
    def __str__(self):
        return self.name


class Video(models.Model):
    """Video content"""
    
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    title = models.CharField(max_length=300)
    description = models.TextField()
    youtube_id = models.CharField(max_length=50, help_text='YouTube video ID (from URL)')
    thumbnail_url = models.URLField(blank=True)
    duration = models.CharField(max_length=20, blank=True, help_text='e.g., 15:30')
    
    category = models.ForeignKey(VideoCategory, on_delete=models.CASCADE, related_name='videos')
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    channel_name = models.CharField(max_length=200, blank=True)
    
    tags = models.JSONField(default=list, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_featured', '-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def embed_url(self):
        return f'https://www.youtube.com/embed/{self.youtube_id}'
    
    @property
    def watch_url(self):
        return f'https://www.youtube.com/watch?v={self.youtube_id}'
    
    def save(self, *args, **kwargs):
        if not self.thumbnail_url:
            self.thumbnail_url = f'https://img.youtube.com/vi/{self.youtube_id}/hqdefault.jpg'
        super().save(*args, **kwargs)


class UserVideoProgress(models.Model):
    """Track user's video watching progress"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_progress')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='user_progress')
    
    is_watched = models.BooleanField(default=False)
    is_favorited = models.BooleanField(default=False)
    watch_time_seconds = models.PositiveIntegerField(default=0)
    
    first_watched_at = models.DateTimeField(auto_now_add=True)
    last_watched_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'video']
        ordering = ['-last_watched_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.video.title[:30]}"