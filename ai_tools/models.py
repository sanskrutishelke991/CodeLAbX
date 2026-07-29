from django.db import models
from django.contrib.auth.models import User


class ChatSession(models.Model):
    """A chat session for a user"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=200, blank=True, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


class ChatMessage(models.Model):
    """Individual message in a chat"""
    
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'AI Assistant'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
class ImageAnalysis(models.Model):
    """User's image analysis history"""
    
    ANALYSIS_TYPES = [
        ('general', 'General Analysis'),
        ('code', 'Code Explanation'),
        ('math', 'Math Problem'),
        ('handwritten', 'Handwritten Notes'),
        ('diagram', 'Diagram/Chart'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='image_analyses')
    image = models.ImageField(upload_to='image_analysis/%Y/%m/')
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES, default='general')
    
    user_question = models.TextField(blank=True, help_text='Optional question about the image')
    ai_analysis = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_analysis_type_display()} - {self.created_at.strftime('%b %d')}"