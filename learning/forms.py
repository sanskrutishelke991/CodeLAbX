"""
Forms for the learning app.
"""

from django import forms
from .models import Roadmap


class RoadmapCreateForm(forms.ModelForm):
    """Form for creating a new learning roadmap."""
    
    TOPIC_CHOICES = [
        ('ML', 'Machine Learning'),
        ('DSA', 'Data Structures & Algorithms'),
    ]
    
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    topic = forms.ChoiceField(
        choices=TOPIC_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'topic'
        })
    )
    
    duration_months = forms.IntegerField(
        min_value=1,
        max_value=12,
        initial=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'duration_months',
            'placeholder': 'e.g., 3'
        })
    )
    
    daily_hours = forms.DecimalField(
        min_value=0.5,
        max_value=8.0,
        decimal_places=1,
        initial=2.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'daily_hours',
            'placeholder': 'e.g., 2.0',
            'step': '0.5'
        })
    )
    
    level = forms.ChoiceField(
        choices=LEVEL_CHOICES,
        initial='beginner',
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'id': 'start_date',
            'type': 'date'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'id': 'description',
            'rows': 3,
            'placeholder': 'Optional: Add a description for your roadmap'
        })
    )
    
    class Meta:
        model = Roadmap
        fields = ['topic', 'duration_months', 'daily_hours', 'level', 'start_date', 'description']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['topic'].label = 'Topic'
        self.fields['duration_months'].label = 'Duration (months)'
        self.fields['daily_hours'].label = 'Daily Study Hours'
        self.fields['level'].label = 'Difficulty Level'
        self.fields['start_date'].label = 'Start Date (optional)'
        self.fields['description'].label = 'Description (optional)'
    
    def clean_duration_months(self):
        duration = self.cleaned_data.get('duration_months')
        if duration and (duration < 1 or duration > 12):
            raise forms.ValidationError('Duration must be between 1 and 12 months.')
        return duration
    
    def clean_daily_hours(self):
        hours = self.cleaned_data.get('daily_hours')
        if hours and (hours < 0.5 or hours > 8.0):
            raise forms.ValidationError('Daily hours must be between 0.5 and 8.0 hours.')
        return hours
