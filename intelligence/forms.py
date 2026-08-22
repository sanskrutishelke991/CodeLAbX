from django import forms

from learning.models import Roadmap

from .models import (
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    SkillPack,
)
from .services.adaptive_roadmaps import (
    PACK_TOPIC_MAP,
    POSTPONE_DAY_CHOICES,
)


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


class AdaptiveRouteProposalForm(forms.Form):
    mission = forms.ModelChoiceField(
        queryset=Mission.objects.none(),
        empty_label="Choose a mission",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    roadmap = forms.ModelChoiceField(
        queryset=Roadmap.objects.none(),
        empty_label="Choose a matching roadmap",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, user, profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mission"].queryset = (
            Mission.objects.filter(user=user, status="proposed")
            .exclude(
                roadmap_revisions__status__in={
                    "proposed",
                    "active",
                    "postponed",
                }
            )
            .select_related("primary_skill")
            .order_by("-created_at")
        )
        topic = PACK_TOPIC_MAP.get(profile.selected_pack.code)
        self.fields["roadmap"].queryset = (
            Roadmap.objects.filter(
                user=user,
                status__in={"active", "paused"},
                topic=topic or "",
            )
            .exclude(
                intelligence_revisions__status__in={"proposed", "postponed"}
            )
            .order_by("-updated_at")
        )


class PostponeRevisionForm(forms.Form):
    days = forms.TypedChoiceField(
        coerce=int,
        choices=[
            (days, f"{days} day{'' if days == 1 else 's'}")
            for days in sorted(POSTPONE_DAY_CHOICES)
        ],
        initial=7,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
