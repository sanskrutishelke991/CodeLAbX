from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from learning.models import Day, Roadmap

from .forms import (
    CommunityReportForm,
    DayCommentForm,
    DiscussionPostForm,
    DiscussionThreadForm,
    GroupInviteForm,
    GroupRoadmapShareForm,
    StudyGroupForm,
)
from .models import (
    CommunityReport,
    DayComment,
    DiscussionPost,
    DiscussionThread,
    GroupInvite,
    GroupMembership,
    GroupRoadmapShare,
    StudyGroup,
    UserBlock,
)
from .services import (
    accept_invite,
    archive_group,
    blocked_user_ids,
    can_access_shared_roadmap,
    create_day_comment,
    create_group,
    create_invite,
    create_post,
    create_thread,
    delete_own_content,
    leave_group,
    moderate_target,
    remove_member,
    report_content,
    require_member,
    require_moderator,
    set_block,
    set_member_role,
    share_roadmap,
    unshare_roadmap,
)


def _member_group(user, group_id):
    return get_object_or_404(
        StudyGroup.objects.filter(memberships__user=user, is_active=True).distinct(),
        id=group_id,
    )


def _handle_access_error(request, exc, redirect_name="community:groups"):
    messages.error(request, str(exc))
    return redirect(redirect_name)


@login_required
def group_list(request):
    groups = (
        StudyGroup.objects.filter(memberships__user=request.user, is_active=True)
        .annotate(member_count=Count("memberships", distinct=True))
        .order_by("-updated_at")
    )
    page_obj = Paginator(groups, 12).get_page(request.GET.get("page"))
    blocks = UserBlock.objects.filter(blocker=request.user).select_related("blocked")
    return render(
        request,
        "community/group_list.html",
        {"groups": page_obj, "page_obj": page_obj, "blocks": blocks},
    )


@login_required
def group_create(request):
    if request.method == "POST":
        form = StudyGroupForm(request.POST)
        if form.is_valid():
            group = create_group(
                request.user,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                max_members=form.cleaned_data["max_members"],
            )
            messages.success(request, "Private study group created.")
            return redirect("community:group_detail", group_id=group.id)
    else:
        form = StudyGroupForm()
    return render(request, "community/group_form.html", {"form": form})


@login_required
def group_detail(request, group_id):
    group = _member_group(request.user, group_id)
    membership = require_member(request.user, group)
    can_moderate = membership.role in {"owner", "moderator"}
    blocked = blocked_user_ids(request.user)
    threads = (
        DiscussionThread.objects.filter(group=group)
        .exclude(author_id__in=blocked)
        .select_related("author")
        .annotate(post_count=Count("posts", filter=Q(posts__is_deleted=False)))
    )
    if not can_moderate:
        threads = threads.filter(is_hidden=False)
    members = list(
        GroupMembership.objects.filter(group=group)
        .select_related("user")
        .order_by("role", "joined_at")
    )
    shares = list(
        GroupRoadmapShare.objects.filter(group=group)
        .select_related("roadmap", "shared_by")
        .order_by("-created_at")
    )
    active_invites = []
    if can_moderate:
        active_invites = list(
            GroupInvite.objects.filter(group=group, is_active=True)
            .select_related("created_by")
            .order_by("-created_at")[:10]
        )
        for invite in active_invites:
            invite.join_url = request.build_absolute_uri(
                reverse("community:join_invite", args=[invite.token])
            )
    return render(
        request,
        "community/group_detail.html",
        {
            "group": group,
            "membership": membership,
            "can_moderate": can_moderate,
            "members": members,
            "threads": threads[:30],
            "roadmap_shares": shares,
            "active_invites": active_invites,
            "invite_form": GroupInviteForm(),
            "roadmap_form": GroupRoadmapShareForm(
                user=request.user,
                group=group,
            ),
            "blocked_ids": blocked,
        },
    )


@login_required
@require_POST
def invite_create(request, group_id):
    group = _member_group(request.user, group_id)
    form = GroupInviteForm(request.POST)
    try:
        require_moderator(request.user, group)
        if not form.is_valid():
            raise ValidationError("Choose a valid invite duration and usage limit.")
        create_invite(
            request.user,
            group,
            expires_days=form.cleaned_data["expires_days"],
            max_uses=form.cleaned_data["max_uses"],
        )
        messages.success(request, "Invite link created.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("community:group_detail", group_id=group.id)


@login_required
def join_invite(request, token):
    invite = get_object_or_404(
        GroupInvite.objects.select_related("group"),
        token=token,
    )
    if request.method == "POST":
        try:
            membership, created = accept_invite(request.user, token)
        except (GroupInvite.DoesNotExist, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Joined private study group."
                if created
                else "You are already a member of this group.",
            )
            return redirect(
                "community:group_detail",
                group_id=membership.group_id,
            )
    return render(
        request,
        "community/join_invite.html",
        {"invite": invite, "usable": invite.is_usable},
    )


@login_required
@require_POST
def roadmap_share(request, group_id):
    group = _member_group(request.user, group_id)
    form = GroupRoadmapShareForm(
        request.POST,
        user=request.user,
        group=group,
    )
    try:
        if not form.is_valid():
            raise ValidationError("Choose one of your unshared roadmaps.")
        share_roadmap(request.user, group, form.cleaned_data["roadmap"])
        messages.success(request, "Roadmap shared privately with the group.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("community:group_detail", group_id=group.id)


@login_required
@require_POST
def roadmap_unshare(request, group_id, share_id):
    group = _member_group(request.user, group_id)
    share = get_object_or_404(GroupRoadmapShare, id=share_id, group=group)
    try:
        unshare_roadmap(request.user, share)
        messages.success(request, "Roadmap removed from the group.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("community:group_detail", group_id=group.id)


@login_required
def thread_create(request, group_id):
    group = _member_group(request.user, group_id)
    if request.method == "POST":
        form = DiscussionThreadForm(request.POST)
        if form.is_valid():
            try:
                thread = create_thread(
                    request.user,
                    group,
                    title=form.cleaned_data["title"],
                    body=form.cleaned_data["body"],
                )
            except (PermissionDenied, ValidationError) as exc:
                messages.error(request, str(exc))
            else:
                return redirect(
                    "community:thread_detail",
                    group_id=group.id,
                    thread_id=thread.id,
                )
    else:
        form = DiscussionThreadForm()
    return render(
        request,
        "community/thread_form.html",
        {"group": group, "form": form},
    )


@login_required
def thread_detail(request, group_id, thread_id):
    group = _member_group(request.user, group_id)
    membership = require_member(request.user, group)
    can_moderate = membership.role in {"owner", "moderator"}
    thread_query = DiscussionThread.objects.filter(group=group).select_related("author")
    if not can_moderate:
        thread_query = thread_query.filter(is_hidden=False)
    thread = get_object_or_404(thread_query, id=thread_id)
    blocked = blocked_user_ids(request.user)
    posts = (
        DiscussionPost.objects.filter(thread=thread)
        .exclude(author_id__in=blocked)
        .select_related("author")
    )
    if not can_moderate:
        posts = posts.filter(is_hidden=False)
    page_obj = Paginator(posts, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "community/thread_detail.html",
        {
            "group": group,
            "thread": thread,
            "posts": page_obj,
            "page_obj": page_obj,
            "post_form": DiscussionPostForm(),
            "report_form": CommunityReportForm(),
            "can_moderate": can_moderate,
        },
    )


@login_required
@require_POST
def post_create(request, group_id, thread_id):
    group = _member_group(request.user, group_id)
    thread = get_object_or_404(DiscussionThread, id=thread_id, group=group)
    form = DiscussionPostForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError("Reply text is required and must fit the limit.")
        create_post(request.user, thread, body=form.cleaned_data["body"])
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect(
        "community:thread_detail",
        group_id=group.id,
        thread_id=thread.id,
    )


@login_required
@require_POST
def post_delete(request, group_id, post_id):
    group = _member_group(request.user, group_id)
    post = get_object_or_404(DiscussionPost, id=post_id, thread__group=group)
    try:
        delete_own_content(request.user, post)
        messages.success(request, "Reply deleted.")
    except PermissionDenied as exc:
        messages.error(request, str(exc))
    return redirect(
        "community:thread_detail",
        group_id=group.id,
        thread_id=post.thread_id,
    )


@login_required
def shared_roadmap(request, group_id, roadmap_id):
    group = _member_group(request.user, group_id)
    roadmap = get_object_or_404(Roadmap, id=roadmap_id)
    if not can_access_shared_roadmap(request.user, group, roadmap):
        raise PermissionDenied
    return render(
        request,
        "community/shared_roadmap.html",
        {
            "group": group,
            "roadmap": roadmap,
            "days": roadmap.days.order_by("day_number"),
        },
    )


@login_required
def shared_day(request, group_id, roadmap_id, day_number):
    group = _member_group(request.user, group_id)
    roadmap = get_object_or_404(Roadmap, id=roadmap_id)
    if not can_access_shared_roadmap(request.user, group, roadmap):
        raise PermissionDenied
    day = get_object_or_404(Day, roadmap=roadmap, day_number=day_number)
    membership = require_member(request.user, group)
    can_moderate = membership.role in {"owner", "moderator"}
    comments = DayComment.objects.filter(day=day, group=group).select_related("author")
    comments = comments.exclude(author_id__in=blocked_user_ids(request.user))
    if not can_moderate:
        comments = comments.filter(is_hidden=False)
    return render(
        request,
        "community/shared_day.html",
        {
            "group": group,
            "roadmap": roadmap,
            "day": day,
            "comments": comments,
            "comment_form": DayCommentForm(),
            "report_form": CommunityReportForm(),
            "can_moderate": can_moderate,
        },
    )


@login_required
@require_POST
def group_day_comment_create(request, group_id, day_id):
    group = _member_group(request.user, group_id)
    day = get_object_or_404(Day.objects.select_related("roadmap"), id=day_id)
    form = DayCommentForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError("Comment text is required and must fit the limit.")
        create_day_comment(
            request.user,
            day,
            body=form.cleaned_data["body"],
            group=group,
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect(
        "community:shared_day",
        group_id=group.id,
        roadmap_id=day.roadmap_id,
        day_number=day.day_number,
    )


@login_required
@require_POST
def personal_day_comment_create(request, day_id):
    day = get_object_or_404(
        Day.objects.select_related("roadmap"),
        id=day_id,
        roadmap__user=request.user,
    )
    form = DayCommentForm(request.POST)
    if form.is_valid():
        create_day_comment(
            request.user,
            day,
            body=form.cleaned_data["body"],
        )
    else:
        messages.error(request, "Comment text is required and must fit the limit.")
    return redirect(
        "learning:day_detail",
        roadmap_id=day.roadmap_id,
        day_number=day.day_number,
    )


@login_required
@require_POST
def day_comment_delete(request, comment_id):
    comment = get_object_or_404(
        DayComment.objects.filter(
            Q(author=request.user) | Q(group__memberships__user=request.user)
        ).distinct(),
        id=comment_id,
    )
    try:
        if comment.group_id:
            require_member(request.user, comment.group)
        delete_own_content(request.user, comment)
        messages.success(request, "Comment deleted.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    if comment.group_id:
        return redirect(
            "community:shared_day",
            group_id=comment.group_id,
            roadmap_id=comment.day.roadmap_id,
            day_number=comment.day.day_number,
        )
    return redirect(
        "learning:day_detail",
        roadmap_id=comment.day.roadmap_id,
        day_number=comment.day.day_number,
    )


@login_required
@require_POST
def content_report(request, group_id, target_type, target_id):
    group = _member_group(request.user, group_id)
    form = CommunityReportForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError("Choose a report reason.")
        _report, created = report_content(
            request.user,
            group,
            target_type=target_type,
            target_id=target_id,
            reason=form.cleaned_data["reason"],
            details=form.cleaned_data["details"],
        )
        messages.success(
            request,
            "Report submitted to group moderators."
            if created
            else "You already reported this content.",
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("community:group_detail", group_id=group.id)


@login_required
def moderation_reports(request, group_id):
    group = _member_group(request.user, group_id)
    require_moderator(request.user, group)
    reports = CommunityReport.objects.filter(group=group).select_related(
        "reporter",
        "resolved_by",
    )
    page_obj = Paginator(reports, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "community/moderation_reports.html",
        {"group": group, "reports": page_obj, "page_obj": page_obj},
    )


@login_required
@require_POST
def moderation_action(request, group_id, report_id, resolution):
    group = _member_group(request.user, group_id)
    report = get_object_or_404(CommunityReport, id=report_id, group=group)
    try:
        moderate_target(request.user, report, resolution=resolution)
        messages.success(request, "Moderation decision recorded.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("community:moderation_reports", group_id=group.id)


@login_required
@require_POST
def member_action(request, group_id, membership_id, action):
    group = _member_group(request.user, group_id)
    membership = get_object_or_404(GroupMembership, id=membership_id, group=group)
    try:
        if action == "remove":
            remove_member(request.user, membership)
        elif action in {"member", "moderator"}:
            set_member_role(request.user, membership, role=action)
        else:
            raise ValidationError("Unsupported member action.")
        messages.success(request, "Group membership updated.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("community:group_detail", group_id=group.id)


@login_required
@require_POST
def group_leave(request, group_id):
    group = _member_group(request.user, group_id)
    try:
        leave_group(request.user, group)
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
        return redirect("community:group_detail", group_id=group.id)
    messages.success(request, "You left the study group.")
    return redirect("community:groups")


@login_required
@require_POST
def user_block_action(request, user_id, action):
    other = get_object_or_404(User, id=user_id)
    try:
        if action == "block":
            set_block(request.user, other, blocked=True)
            messages.success(request, "User blocked. Their group content is hidden from you.")
        elif action == "unblock":
            set_block(request.user, other, blocked=False)
            messages.success(request, "User unblocked.")
        else:
            raise ValidationError("Unsupported block action.")
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect("community:groups")


@login_required
@require_POST
def group_archive(request, group_id):
    group = _member_group(request.user, group_id)
    try:
        archive_group(request.user, group)
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, str(exc))
        return redirect("community:group_detail", group_id=group.id)
    messages.success(request, "Study group archived and invite links disabled.")
    return redirect("community:groups")
