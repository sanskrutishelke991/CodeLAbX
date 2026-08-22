from django import forms

from .models import LearnerIntelligenceProfile, LearningEvent, SkillPack


class IntelligenceOnboardingForm(forms.ModelForm):
    class Meta:
        model = LearnerIntelligenceProfile
        fields = ["primary_goal", "custom_goal", "selected_pack"]
        widgets = {
            "primary_goal": forms.Select(attrs={"class": "form-select"}),
            "custom_goal": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 300,
                    "placeholder": "Optional unless Custom goal is selected",
                }
            ),
            "selected_pack": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["selected_pack"].queryset = (
            SkillPack.objects.filter(is_active=True)
            .exclude(code="shared_core")
            .order_by("name", "-version")
        )
        self.fields["primary_goal"].label = "Primary college goal"
        self.fields["selected_pack"].label = "Starting skill pack"
        self.fields["custom_goal"].required = False

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("primary_goal") == "custom"
            and not (cleaned.get("custom_goal") or "").strip()
        ):
            self.add_error("custom_goal", "Describe your custom goal.")
        return cleaned


class EvidenceFilterForm(forms.Form):
    skill = forms.ChoiceField(
        required=False,
        choices=[("", "All skills")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    event_type = forms.ChoiceField(
        required=False,
        choices=[("", "All evidence types"), *LearningEvent.EVENT_TYPES],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, skill_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["skill"].choices = [
            ("", "All skills"),
            *skill_choices,
        ]
