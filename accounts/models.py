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