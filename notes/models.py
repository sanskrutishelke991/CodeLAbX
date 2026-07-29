from django.db import models
from django.contrib.auth.models import User


class Note(models.Model):
    """User's personal notes"""
    
    COLOR_CHOICES = [
        ('purple', 'Purple'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('red', 'Red'),
        ('yellow', 'Yellow'),
        ('pink', 'Pink'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    content = models.TextField()
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='purple')
    tags = models.JSONField(default=list, blank=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_pinned', '-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    @property
    def color_hex(self):
        colors = {
            'purple': '#6C63FF',
            'blue': '#4a90e2',
            'green': '#00D4AA',
            'red': '#FF6B6B',
            'yellow': '#f59e0b',
            'pink': '#ec4899',
        }
        return colors.get(self.color, '#6C63FF')
    
    @property
    def content_preview(self):
        """Return first 150 chars of content"""
        return self.content[:150] + '...' if len(self.content) > 150 else self.content


class Bookmark(models.Model):
    """Bookmark for any content"""
    
    BOOKMARK_TYPES = [
        ('day', 'Learning Day'),
        ('roadmap', 'Roadmap'),
        ('test', 'Test'),
        ('code', 'Code Review'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    title = models.CharField(max_length=200)
    url = models.CharField(max_length=500)
    bookmark_type = models.CharField(max_length=20, choices=BOOKMARK_TYPES, default='other')
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, default='🔖')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"