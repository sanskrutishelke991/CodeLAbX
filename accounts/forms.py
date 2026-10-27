from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import EmailPreference, GitHubConnection, UserProfile


class ProfileUpdateForm(forms.ModelForm):
    """Form to update user profile"""
    
    skills_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Python, Django, AI, ML (comma separated)'
        }),
        help_text='Enter skills separated by commas'
    )
    
    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'bio', 'location',
            'github_url', 'linkedin_url', 'twitter_url', 'website_url',
            'learning_goals', 'is_public'
        ]
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Tell us about yourself...',
                'maxlength': 500
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Mumbai, India'
            }),
            'github_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/username'
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://linkedin.com/in/username'
            }),
            'twitter_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://twitter.com/username'
            }),
            'website_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://yourwebsite.com'
            }),
            'learning_goals': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'What are you learning? What are your goals?'
            }),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill skills from list
        if self.instance and self.instance.skills:
            self.fields['skills_input'].initial = ', '.join(self.instance.skills)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Parse skills from comma-separated string
        skills_str = self.cleaned_data.get('skills_input', '')
        if skills_str:
            skills = [s.strip() for s in skills_str.split(',') if s.strip()]
            instance.skills = skills
        else:
            instance.skills = []
        
        if commit:
            instance.save()
        return instance

class RegistrationForm(UserCreationForm):
    """Create an account with a unique, normalized email address."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "you@example.com",
                "autocomplete": "email",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already uses this email address.")
        return email


class EmailPreferenceForm(forms.ModelForm):
    class Meta:
        model = EmailPreference
        fields = [
            "weekly_report_enabled",
            "report_weekday",
            "include_activity",
            "include_skill_progress",
            "include_next_steps",
        ]
        widgets = {
            "weekly_report_enabled": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "report_weekday": forms.Select(attrs={"class": "form-select"}),
            "include_activity": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "include_skill_progress": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "include_next_steps": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.instance.user = user
        self.fields["weekly_report_enabled"].label = (
            "Email me one weekly learning report"
        )
        self.fields["include_activity"].label = "Recorded activity"
        self.fields["include_skill_progress"].label = (
            "Learning DNA and Skill Passport summary"
        )
        self.fields["include_next_steps"].label = (
            "Current mission and retention next steps"
        )

    def save(self, commit=True):
        preference = super().save(commit=False)
        preference.user = self.user
        if commit:
            preference.save()
        return preference


class GitHubConnectionForm(forms.ModelForm):
    class Meta:
        model = GitHubConnection
        fields = ["username"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 39,
                    "autocomplete": "off",
                    "placeholder": "public-github-username",
                }
            )
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.instance.user = user

    def save(self, commit=True):
        connection = super().save(commit=False)
        connection.user = self.user
        if commit:
            connection.save()
        return connection
