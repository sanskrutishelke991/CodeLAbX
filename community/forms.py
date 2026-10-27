from django import forms

from learning.models import Roadmap

from .models import (
    CommunityReport,
    DayComment,
    DiscussionPost,
    DiscussionThread,
    StudyGroup,
)


class StudyGroupForm(forms.ModelForm):
    class Meta:
        model = StudyGroup
        fields = ["name", "description", "max_members"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "maxlength": 100}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "maxlength": 500}
            ),
            "max_members": forms.NumberInput(
                attrs={"class": "form-control", "min": 2, "max": 100}
            ),
        }


class GroupInviteForm(forms.Form):
    expires_days = forms.TypedChoiceField(
        coerce=int,
        choices=[(1, "1 day"), (3, "3 days"), (7, "7 days")],
        initial=3,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    max_uses = forms.IntegerField(
        min_value=1,
        max_value=25,
        initial=10,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 1, "max": 25}
        ),
    )


class GroupRoadmapShareForm(forms.Form):
    roadmap = forms.ModelChoiceField(
        queryset=Roadmap.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, user, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roadmap"].queryset = (
            Roadmap.objects.filter(user=user)
            .exclude(group_shares__group=group)
            .order_by("-updated_at")
        )


class DiscussionThreadForm(forms.ModelForm):
    class Meta:
        model = DiscussionThread
        fields = ["title", "body"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 180}),
            "body": forms.Textarea(
                attrs={"class": "form-control", "rows": 6, "maxlength": 3000}
            ),
        }


class DiscussionPostForm(forms.ModelForm):
    class Meta:
        model = DiscussionPost
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "maxlength": 2500}
            )
        }


class DayCommentForm(forms.ModelForm):
    class Meta:
        model = DayComment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "maxlength": 1200}
            )
        }


class CommunityReportForm(forms.Form):
    reason = forms.ChoiceField(
        choices=CommunityReport.REASON_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    details = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "maxlength": 500}
        ),
    )
