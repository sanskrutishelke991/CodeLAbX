from django import forms

from ai_tools.models import ChatMessage, ChatSession
from learning.models import Roadmap

from .models import (
    LearnerIntelligenceProfile,
    LearningEvent,
    Mission,
    SkillPack,
    TutorFeedback,
    TutorMemory,
    TutorPreference,
)
from .services.adaptive_roadmaps import (
    PACK_TOPIC_MAP,
    POSTPONE_DAY_CHOICES,
)
from .services.tutor_context import MAX_ACTIVE_MEMORIES


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


class TutorPreferenceForm(forms.ModelForm):
    SESSION_CHOICES = [
        (15, "15 minutes"),
        (25, "25 minutes"),
        (40, "40 minutes"),
        (60, "60 minutes"),
        (90, "90 minutes"),
    ]
    session_minutes = forms.TypedChoiceField(
        coerce=int,
        choices=SESSION_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    avoid_emoji = forms.BooleanField(required=False)
    prefer_checklists = forms.BooleanField(required=False)
    reduce_cognitive_load = forms.BooleanField(required=False)

    class Meta:
        model = TutorPreference
        fields = [
            "explanation_depth",
            "teaching_mode",
            "code_density",
            "preferred_language",
            "pace",
            "session_minutes",
            "learning_context_enabled",
            "observed_adaptation_enabled",
        ]
        widgets = {
            "explanation_depth": forms.Select(attrs={"class": "form-select"}),
            "teaching_mode": forms.Select(attrs={"class": "form-select"}),
            "code_density": forms.Select(attrs={"class": "form-select"}),
            "preferred_language": forms.Select(attrs={"class": "form-select"}),
            "pace": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accessibility = (
            self.instance.accessibility_preferences
            if self.instance and self.instance.pk
            else {}
        )
        for key in (
            "avoid_emoji",
            "prefer_checklists",
            "reduce_cognitive_load",
        ):
            self.fields[key].initial = bool(accessibility.get(key))

    def save(self, commit=True):
        preference = super().save(commit=False)
        preference.accessibility_preferences = {
            "avoid_emoji": self.cleaned_data["avoid_emoji"],
            "prefer_checklists": self.cleaned_data["prefer_checklists"],
            "reduce_cognitive_load": self.cleaned_data[
                "reduce_cognitive_load"
            ],
        }
        if commit:
            preference.save()
        return preference


class TutorMemoryForm(forms.ModelForm):
    chat_session = forms.ModelChoiceField(
        queryset=ChatSession.objects.none(),
        required=False,
        empty_label="No chat session",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = TutorMemory
        fields = [
            "category",
            "content",
            "reason",
            "chat_session",
            "is_active",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "maxlength": 600,
                }
            ),
            "reason": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 300}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.instance.user = user
        recent_session_ids = list(
            ChatSession.objects.filter(user=user)
            .order_by("-updated_at")
            .values_list("id", flat=True)[:25]
        )
        self.fields["chat_session"].queryset = (
            ChatSession.objects.filter(id__in=recent_session_ids)
            .order_by("-updated_at")
        )
        self.fields["content"].help_text = (
            "Maximum 600 characters. Never store passwords, tokens, API keys, "
            "private repository content, or sensitive personal data."
        )
        self.fields["reason"].help_text = (
            "Explain why the tutor should use this context."
        )

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        chat_session = cleaned.get("chat_session")
        if category == "session_summary" and chat_session is None:
            self.add_error(
                "chat_session",
                "Choose the conversation summarized by this memory.",
            )
        if category != "session_summary" and chat_session is not None:
            self.add_error(
                "chat_session",
                "Only a session summary can reference a conversation.",
            )
        if category == "session_summary" and chat_session is not None:
            duplicate = TutorMemory.objects.filter(
                user=self.user,
                category="session_summary",
                chat_session=chat_session,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    "chat_session",
                    "That conversation already has a tutor summary.",
                )
        wants_active = cleaned.get("is_active", False)
        was_active = bool(self.instance.pk and self.instance.is_active)
        if wants_active and not was_active:
            active_count = TutorMemory.objects.filter(
                user=self.user,
                is_active=True,
            ).count()
            if active_count >= MAX_ACTIVE_MEMORIES:
                self.add_error(
                    "is_active",
                    f"At most {MAX_ACTIVE_MEMORIES} active memories are allowed.",
                )
        return cleaned

    def save(self, commit=True):
        memory = super().save(commit=False)
        memory.user = self.user
        if not memory.pk:
            memory.source_type = "explicit_user"
        memory.user_confirmed = True
        if memory.category == "session_summary":
            memory.source_key = f"session-summary:{memory.chat_session_id}"
        elif not memory.pk or memory.source_key.startswith("session-summary:"):
            memory.source_key = ""
        if commit:
            memory.save()
        return memory


class TutorFeedbackForm(forms.Form):
    message = forms.ModelChoiceField(queryset=ChatMessage.objects.none())
    feedback_type = forms.ChoiceField(choices=TutorFeedback.FEEDBACK_CHOICES)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].queryset = ChatMessage.objects.filter(
            session__user=user,
            role="assistant",
        )
