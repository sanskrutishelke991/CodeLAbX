from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from learning.models import Day, Roadmap

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


def membership_for(user, group):
    return GroupMembership.objects.filter(user=user, group=group).first()


def require_member(user, group):
    membership = membership_for(user, group)
    if membership is None or not group.is_active:
        raise PermissionDenied("Active study-group membership is required.")
    return membership


def require_moderator(user, group):
    membership = require_member(user, group)
    if membership.role not in {"owner", "moderator"}:
        raise PermissionDenied("Group moderator access is required.")
    return membership


def users_block_each_other(first, second):
    return UserBlock.objects.filter(
        Q(blocker=first, blocked=second) | Q(blocker=second, blocked=first)
    ).exists()


def blocked_user_ids(user):
    outgoing = UserBlock.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    incoming = UserBlock.objects.filter(blocked=user).values_list("blocker_id", flat=True)
    return set(outgoing).union(incoming)


@transaction.atomic
def create_group(user, *, name, description="", max_members=25):
    group = StudyGroup.objects.create(
        owner=user,
        name=name,
        description=description,
        max_members=max_members,
    )
    GroupMembership.objects.create(group=group, user=user, role="owner")
    return group


@transaction.atomic
def create_invite(user, group, *, expires_days, max_uses):
    require_moderator(user, group)
    return GroupInvite.objects.create(
        group=group,
        created_by=user,
        expires_at=timezone.now() + timedelta(days=expires_days),
        max_uses=max_uses,
    )


@transaction.atomic
def accept_invite(user, token):
    invite = (
        GroupInvite.objects.select_for_update()
        .select_related("group")
        .get(token=token)
    )
    group = StudyGroup.objects.select_for_update().get(id=invite.group_id)
    existing = GroupMembership.objects.filter(group=group, user=user).first()
    if existing:
        return existing, False
    if not invite.is_usable or not group.is_active:
        raise ValidationError("This study-group invite is expired or unavailable.")
    if GroupMembership.objects.filter(group=group).count() >= group.max_members:
        raise ValidationError("This study group has reached its member limit.")
    membership = GroupMembership.objects.create(
        group=group,
        user=user,
        role="member",
    )
    invite.use_count += 1
    if invite.use_count >= invite.max_uses:
        invite.is_active = False
    invite.save(update_fields=["use_count", "is_active"])
    return membership, True


@transaction.atomic
def share_roadmap(user, group, roadmap):
    require_member(user, group)
    if not isinstance(roadmap, Roadmap) or roadmap.user_id != user.id:
        raise ValidationError("Only the roadmap owner can share this roadmap.")
    share, created = GroupRoadmapShare.objects.get_or_create(
        group=group,
        roadmap=roadmap,
        defaults={"shared_by": user},
    )
    return share, created


@transaction.atomic
def unshare_roadmap(user, share):
    require_moderator(user, share.group)
    if share.shared_by_id != user.id and share.group.owner_id != user.id:
        raise PermissionDenied("Only the roadmap owner or group owner can unshare it.")
    share.delete()


def can_access_shared_roadmap(user, group, roadmap):
    return bool(
        membership_for(user, group)
        and GroupRoadmapShare.objects.filter(group=group, roadmap=roadmap).exists()
    )


@transaction.atomic
def create_thread(user, group, *, title, body):
    require_member(user, group)
    return DiscussionThread.objects.create(
        group=group,
        author=user,
        title=title,
        body=body,
    )


@transaction.atomic
def create_post(user, thread, *, body):
    require_member(user, thread.group)
    if thread.is_locked or thread.is_hidden:
        raise ValidationError("This discussion thread is not accepting replies.")
    if users_block_each_other(user, thread.author):
        raise PermissionDenied("Blocked users cannot reply to each other.")
    return DiscussionPost.objects.create(
        thread=thread,
        author=user,
        body=body,
    )


@transaction.atomic
def create_day_comment(user, day, *, body, group=None):
    if not isinstance(day, Day):
        raise ValidationError("A valid roadmap day is required.")
    if group is None:
        if day.roadmap.user_id != user.id:
            raise PermissionDenied("Only the roadmap owner can add personal comments.")
    else:
        require_member(user, group)
        if not GroupRoadmapShare.objects.filter(
            group=group,
            roadmap=day.roadmap,
        ).exists():
            raise PermissionDenied("This roadmap is not shared with the group.")
        if users_block_each_other(user, day.roadmap.user):
            raise PermissionDenied("Blocked users cannot comment on each other's roadmaps.")
    return DayComment.objects.create(
        day=day,
        group=group,
        author=user,
        body=body,
    )


def _target_for_report(group, target_type, target_id):
    mapping = {
        "thread": DiscussionThread,
        "post": DiscussionPost,
        "day_comment": DayComment,
    }
    model = mapping.get(target_type)
    if model is None:
        raise ValidationError("Unsupported report target.")
    query = model.objects.filter(id=target_id)
    if target_type == "thread":
        query = query.filter(group=group)
    elif target_type == "post":
        query = query.filter(thread__group=group)
    else:
        query = query.filter(group=group)
    target = query.first()
    if target is None:
        raise ValidationError("The reported content is unavailable.")
    return target


@transaction.atomic
def report_content(
    user,
    group,
    *,
    target_type,
    target_id,
    reason,
    details="",
):
    require_member(user, group)
    _target_for_report(group, target_type, target_id)
    report, created = CommunityReport.objects.get_or_create(
        reporter=user,
        target_type=target_type,
        target_id=target_id,
        defaults={
            "group": group,
            "reason": reason,
            "details": details,
        },
    )
    return report, created


@transaction.atomic
def moderate_target(user, report, *, resolution):
    require_moderator(user, report.group)
    report = CommunityReport.objects.select_for_update().get(id=report.id)
    if report.status != "open":
        raise ValidationError("This report has already been reviewed.")
    if resolution == "hide":
        target = _target_for_report(
            report.group,
            report.target_type,
            report.target_id,
        )
        target.is_hidden = True
        target.hidden_by = user
        target.hidden_at = timezone.now()
        target.save()
        report.status = "resolved"
    elif resolution == "dismiss":
        report.status = "dismissed"
    else:
        raise ValidationError("Unsupported moderation action.")
    report.resolved_by = user
    report.resolved_at = timezone.now()
    report.save()
    return report


@transaction.atomic
def delete_own_content(user, target):
    if target.author_id != user.id:
        raise PermissionDenied("Only the author can delete this content.")
    target.is_deleted = True
    target.body = ""
    target.save()
    return target


@transaction.atomic
def set_block(user, other_user, *, blocked):
    if user.id == other_user.id:
        raise ValidationError("You cannot block yourself.")
    if blocked:
        block, created = UserBlock.objects.get_or_create(
            blocker=user,
            blocked=other_user,
        )
        return block, created
    deleted, _ = UserBlock.objects.filter(
        blocker=user,
        blocked=other_user,
    ).delete()
    return None, bool(deleted)


@transaction.atomic
def remove_member(actor, membership):
    actor_membership = require_moderator(actor, membership.group)
    if membership.role == "owner":
        raise ValidationError("The group owner cannot be removed.")
    if actor_membership.role == "moderator" and membership.role != "member":
        raise PermissionDenied("Moderators can remove members only.")
    membership.delete()


@transaction.atomic
def leave_group(user, group):
    membership = require_member(user, group)
    if membership.role == "owner":
        raise ValidationError("The owner must archive the group instead of leaving.")
    membership.delete()


@transaction.atomic
def set_member_role(actor, membership, *, role):
    actor_membership = require_member(actor, membership.group)
    if actor_membership.role != "owner":
        raise PermissionDenied("Only the group owner can change moderator roles.")
    if membership.role == "owner":
        raise ValidationError("The owner role cannot be changed.")
    if role not in {"member", "moderator"}:
        raise ValidationError("Unsupported group role.")
    membership.role = role
    membership.save()
    return membership


@transaction.atomic
def archive_group(user, group):
    membership = require_member(user, group)
    if membership.role != "owner":
        raise PermissionDenied("Only the group owner can archive the group.")
    group.is_active = False
    group.save(update_fields=["is_active", "updated_at"])
    GroupInvite.objects.filter(group=group, is_active=True).update(is_active=False)
    return group
