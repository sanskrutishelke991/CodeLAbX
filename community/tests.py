from __future__ import annotations

from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
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
from .services import (
    accept_invite,
    archive_group,
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
    set_block,
    set_member_role,
    share_roadmap,
    users_block_each_other,
)


def roadmap_for(user):
    roadmap = Roadmap.objects.create(
        user=user,
        topic="DSA",
        title=f"{user.username} private roadmap",
        description="PRIVATE_ROADMAP_DESCRIPTION",
        total_days=1,
        daily_hours=1,
    )
    day = Day.objects.create(
        roadmap=roadmap,
        day_number=1,
        title="Arrays",
        description="PRIVATE_DAY_DESCRIPTION",
        estimated_hours=1,
        order=1,
        ai_content="PRIVATE_AI_LESSON",
    )
    return roadmap, day


class CommunityServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="group-owner", password="StrongPass123!"
        )
        self.member = User.objects.create_user(
            username="group-member", password="StrongPass123!"
        )
        self.other = User.objects.create_user(
            username="group-other", password="StrongPass123!"
        )
        self.group = create_group(
            self.owner,
            name="Private Algorithms",
            description="Invite-only study",
            max_members=3,
        )
        self.roadmap, self.day = roadmap_for(self.owner)

    def join_member(self):
        invite = create_invite(
            self.owner,
            self.group,
            expires_days=3,
            max_uses=2,
        )
        return accept_invite(self.member, invite.token)[0], invite

    def test_group_creation_is_private_and_owner_membership_atomic(self):
        membership = GroupMembership.objects.get(group=self.group)
        self.assertEqual(membership.user, self.owner)
        self.assertEqual(membership.role, "owner")
        self.assertFalse(
            StudyGroup.objects.filter(
                id=self.group.id,
                memberships__user=self.other,
            ).exists()
        )

    def test_invite_is_bounded_idempotent_and_member_limit_enforced(self):
        membership, invite = self.join_member()
        duplicate, created = accept_invite(self.member, invite.token)
        self.assertFalse(created)
        self.assertEqual(duplicate.id, membership.id)
        invite.refresh_from_db()
        self.assertEqual(invite.use_count, 1)
        accept_invite(self.other, invite.token)
        invite.refresh_from_db()
        self.assertFalse(invite.is_active)
        fourth = User.objects.create_user(
            username="group-fourth", password="StrongPass123!"
        )
        with self.assertRaises(ValidationError):
            accept_invite(fourth, invite.token)

    def test_only_owner_can_promote_and_owner_cannot_be_removed(self):
        membership, _ = self.join_member()
        set_member_role(self.owner, membership, role="moderator")
        membership.refresh_from_db()
        self.assertEqual(membership.role, "moderator")
        owner_membership = GroupMembership.objects.get(
            group=self.group, user=self.owner
        )
        with self.assertRaises(ValidationError):
            remove_member(self.owner, owner_membership)
        with self.assertRaises(ValidationError):
            leave_group(self.owner, self.group)

    def test_only_owner_can_archive_and_invites_are_disabled(self):
        _membership, invite = self.join_member()
        with self.assertRaises(PermissionDenied):
            archive_group(self.member, self.group)
        archive_group(self.owner, self.group)
        self.group.refresh_from_db()
        invite.refresh_from_db()
        self.assertFalse(self.group.is_active)
        self.assertFalse(invite.is_active)

    def test_roadmap_share_requires_owner_and_membership(self):
        self.join_member()
        share, created = share_roadmap(self.owner, self.group, self.roadmap)
        self.assertTrue(created)
        self.assertEqual(share.shared_by, self.owner)
        member_roadmap, _ = roadmap_for(self.member)
        with self.assertRaises(ValidationError):
            share_roadmap(self.owner, self.group, member_roadmap)
        with self.assertRaises(PermissionDenied):
            share_roadmap(self.other, self.group, self.roadmap)

    def test_forum_posts_respect_membership_locking_and_user_blocks(self):
        self.join_member()
        thread = create_thread(
            self.owner,
            self.group,
            title="Two pointers",
            body="Discuss the invariant.",
        )
        post = create_post(self.member, thread, body="Keep left and right bounded.")
        self.assertEqual(post.author, self.member)
        set_block(self.owner, self.member, blocked=True)
        self.assertTrue(users_block_each_other(self.owner, self.member))
        with self.assertRaises(PermissionDenied):
            create_post(self.member, thread, body="Blocked reply")
        set_block(self.owner, self.member, blocked=False)
        thread.is_locked = True
        thread.save()
        with self.assertRaises(ValidationError):
            create_post(self.member, thread, body="Locked reply")

    def test_personal_and_group_day_comments_have_distinct_access(self):
        self.join_member()
        personal = create_day_comment(
            self.owner,
            self.day,
            body="Private owner reflection.",
        )
        self.assertIsNone(personal.group)
        with self.assertRaises(PermissionDenied):
            create_day_comment(self.member, self.day, body="Not owner")
        share_roadmap(self.owner, self.group, self.roadmap)
        group_comment = create_day_comment(
            self.member,
            self.day,
            group=self.group,
            body="Group-visible question.",
        )
        self.assertEqual(group_comment.group, self.group)
        self.assertEqual(DayComment.objects.count(), 2)

    def test_reports_are_unique_and_moderation_hides_target(self):
        self.join_member()
        thread = create_thread(
            self.owner,
            self.group,
            title="Reportable",
            body="Content requiring review.",
        )
        post = create_post(self.member, thread, body="Potential private information")
        report, created = report_content(
            self.owner,
            self.group,
            target_type="post",
            target_id=post.id,
            reason="privacy",
        )
        self.assertTrue(created)
        duplicate, duplicate_created = report_content(
            self.owner,
            self.group,
            target_type="post",
            target_id=post.id,
            reason="privacy",
        )
        self.assertFalse(duplicate_created)
        self.assertEqual(report.id, duplicate.id)
        GroupMembership.objects.filter(group=self.group, user=self.member).delete()
        moderate_target(self.owner, report, resolution="hide")
        post.refresh_from_db()
        report.refresh_from_db()
        self.assertTrue(post.is_hidden)
        self.assertEqual(report.status, "resolved")

    def test_author_delete_blanks_content_without_cross_user_delete(self):
        self.join_member()
        thread = create_thread(
            self.owner, self.group, title="Delete", body="Delete test"
        )
        post = create_post(self.member, thread, body="Remove me")
        with self.assertRaises(PermissionDenied):
            delete_own_content(self.owner, post)
        delete_own_content(self.member, post)
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)
        self.assertEqual(post.body, "")

    def test_operational_models_are_registered_in_admin(self):
        for model in (
            StudyGroup,
            GroupMembership,
            GroupInvite,
            GroupRoadmapShare,
            DiscussionThread,
            DiscussionPost,
            DayComment,
            UserBlock,
            CommunityReport,
        ):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)


class CommunityViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="view-owner", password="StrongPass123!"
        )
        self.member = User.objects.create_user(
            username="view-member", password="StrongPass123!"
        )
        self.outsider = User.objects.create_user(
            username="view-outsider", password="StrongPass123!"
        )
        self.group = create_group(
            self.owner,
            name="Private Web Group",
            description="Invite only",
            max_members=10,
        )
        self.roadmap, self.day = roadmap_for(self.owner)
        invite = create_invite(
            self.owner, self.group, expires_days=3, max_uses=5
        )
        accept_invite(self.member, invite.token)
        self.invite = invite
        self.client.force_login(self.owner)

    def test_group_list_and_detail_are_membership_scoped(self):
        response = self.client.get(reverse("community:groups"))
        self.assertContains(response, self.group.name)
        self.client.force_login(self.outsider)
        detail = self.client.get(
            reverse("community:group_detail", args=[self.group.id])
        )
        self.assertEqual(detail.status_code, 404)
        listing = self.client.get(reverse("community:groups"))
        self.assertNotContains(listing, self.group.name)

    def test_create_group_and_invite_accept_are_real_post_flows(self):
        self.client.force_login(self.outsider)
        created = self.client.post(
            reverse("community:group_create"),
            {
                "name": "New private group",
                "description": "Safe group",
                "max_members": 8,
            },
        )
        self.assertEqual(created.status_code, 302)
        group = StudyGroup.objects.get(name="New private group")
        self.assertTrue(
            GroupMembership.objects.filter(
                group=group, user=self.outsider, role="owner"
            ).exists()
        )
        self.client.force_login(self.member)
        join_url = reverse("community:join_invite", args=[self.invite.token])
        page = self.client.get(join_url)
        self.assertContains(page, self.group.name)
        joined = self.client.post(join_url)
        self.assertEqual(joined.status_code, 302)

    def test_thread_and_reply_escape_untrusted_html(self):
        thread = create_thread(
            self.owner,
            self.group,
            title="<script>thread</script>",
            body="<img src=x onerror=alert(1)>",
        )
        create_post(
            self.member,
            thread,
            body="<script>reply()</script>",
        )
        response = self.client.get(
            reverse(
                "community:thread_detail",
                args=[self.group.id, thread.id],
            )
        )
        self.assertContains(response, "&lt;script&gt;thread&lt;/script&gt;")
        self.assertContains(response, "&lt;script&gt;reply()&lt;/script&gt;")
        self.assertNotContains(response, "<script>thread</script>")
        self.assertNotContains(response, "<img src=x")
        self.assertContains(response, "&lt;img src=x onerror=alert(1)&gt;")

    def test_shared_roadmap_hides_private_descriptions_and_ai_content(self):
        share_roadmap(self.owner, self.group, self.roadmap)
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(
                "community:shared_roadmap",
                args=[self.group.id, self.roadmap.id],
            )
        )
        self.assertContains(response, self.day.title)
        self.assertNotContains(response, "PRIVATE_ROADMAP_DESCRIPTION")
        self.assertNotContains(response, "PRIVATE_DAY_DESCRIPTION")
        self.assertNotContains(response, "PRIVATE_AI_LESSON")

    def test_owner_and_group_day_comment_views_are_separate(self):
        share_roadmap(self.owner, self.group, self.roadmap)
        personal_url = reverse(
            "community:personal_day_comment_create", args=[self.day.id]
        )
        self.client.post(personal_url, {"body": "Owner-private comment"})
        self.client.force_login(self.member)
        group_url = reverse(
            "community:group_day_comment_create",
            args=[self.group.id, self.day.id],
        )
        self.client.post(group_url, {"body": "Group comment"})
        shared = self.client.get(
            reverse(
                "community:shared_day",
                args=[self.group.id, self.roadmap.id, self.day.day_number],
            )
        )
        self.assertContains(shared, "Group comment")
        self.assertNotContains(shared, "Owner-private comment")
        self.client.force_login(self.owner)
        owner_page = self.client.get(
            reverse(
                "learning:day_detail",
                args=[self.roadmap.id, self.day.day_number],
            )
        )
        self.assertContains(owner_page, "Owner-private comment")

    def test_invite_and_roadmap_mutations_are_post_only(self):
        invite_url = reverse("community:invite_create", args=[self.group.id])
        share_url = reverse("community:roadmap_share", args=[self.group.id])
        self.assertEqual(self.client.get(invite_url).status_code, 405)
        self.assertEqual(self.client.get(share_url).status_code, 405)
        self.client.post(invite_url, {"expires_days": 3, "max_uses": 2})
        self.assertGreater(GroupInvite.objects.filter(group=self.group).count(), 1)
        self.client.post(share_url, {"roadmap": self.roadmap.id})
        share = GroupRoadmapShare.objects.get(group=self.group, roadmap=self.roadmap)
        unshare_url = reverse(
            "community:roadmap_unshare", args=[self.group.id, share.id]
        )
        self.assertEqual(self.client.get(unshare_url).status_code, 405)
        self.client.post(unshare_url)
        self.assertFalse(GroupRoadmapShare.objects.filter(id=share.id).exists())

    def test_thread_reply_and_author_delete_endpoints(self):
        create_url = reverse("community:thread_create", args=[self.group.id])
        created = self.client.post(
            create_url,
            {"title": "Endpoint thread", "body": "Bounded body"},
        )
        thread = DiscussionThread.objects.get(title="Endpoint thread")
        self.assertRedirects(
            created,
            reverse("community:thread_detail", args=[self.group.id, thread.id]),
        )
        self.client.force_login(self.member)
        reply_url = reverse(
            "community:post_create", args=[self.group.id, thread.id]
        )
        self.assertEqual(self.client.get(reply_url).status_code, 405)
        self.client.post(reply_url, {"body": "Endpoint reply"})
        post = DiscussionPost.objects.get(thread=thread)
        delete_url = reverse(
            "community:post_delete", args=[self.group.id, post.id]
        )
        self.client.post(delete_url)
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)

    def test_owner_role_controls_and_group_archive_endpoint(self):
        membership = GroupMembership.objects.get(group=self.group, user=self.member)
        promote = reverse(
            "community:member_action",
            args=[self.group.id, membership.id, "moderator"],
        )
        self.assertEqual(self.client.get(promote).status_code, 405)
        self.client.post(promote)
        membership.refresh_from_db()
        self.assertEqual(membership.role, "moderator")
        self.client.post(
            reverse(
                "community:member_action",
                args=[self.group.id, membership.id, "member"],
            )
        )
        archive_url = reverse("community:group_archive", args=[self.group.id])
        self.assertEqual(self.client.get(archive_url).status_code, 405)
        self.client.post(archive_url)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_active)

    def test_member_cannot_open_moderation_queue(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("community:moderation_reports", args=[self.group.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_report_and_moderation_endpoints_are_post_only(self):
        thread = create_thread(
            self.member,
            self.group,
            title="Moderate",
            body="Review this",
        )
        report_url = reverse(
            "community:content_report",
            args=[self.group.id, "thread", thread.id],
        )
        self.assertEqual(self.client.get(report_url).status_code, 405)
        self.client.post(report_url, {"reason": "unsafe", "details": "Review"})
        report = CommunityReport.objects.get()
        action_url = reverse(
            "community:moderation_action",
            args=[self.group.id, report.id, "hide"],
        )
        self.assertEqual(self.client.get(action_url).status_code, 405)
        self.client.post(action_url)
        thread.refresh_from_db()
        self.assertTrue(thread.is_hidden)

    def test_block_hides_content_and_unblock_is_available(self):
        thread = create_thread(
            self.member, self.group, title="Hidden by block", body="Body"
        )
        self.client.post(
            reverse(
                "community:user_block_action",
                args=[self.member.id, "block"],
            )
        )
        detail = self.client.get(
            reverse("community:group_detail", args=[self.group.id])
        )
        self.assertNotContains(detail, thread.title)
        listing = self.client.get(reverse("community:groups"))
        self.assertContains(listing, "Unblock")

    def test_no_public_discovery_or_direct_message_claims(self):
        self.client.logout()
        response = self.client.get(reverse("community:groups"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.owner)
        detail = self.client.get(
            reverse("community:group_detail", args=[self.group.id])
        )
        self.assertContains(detail, "No public discovery")
        self.assertContains(detail, "no direct messages")

    def test_account_export_contains_owned_community_data_without_invite_token(self):
        thread = create_thread(
            self.owner, self.group, title="Export thread", body="Export body"
        )
        self.client.force_login(self.owner)
        response = self.client.post(reverse("accounts:export_account_data"))
        data = response.json()["community"]
        self.assertEqual(data["owned_groups"][0]["name"], self.group.name)
        self.assertEqual(data["threads"][0]["id"], thread.id)
        self.assertNotIn("group_invites", data)
        self.assertNotIn(str(self.invite.token), response.content.decode())

    def test_group_detail_query_count_is_bounded(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("community:group_detail", args=[self.group.id])
            )
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(queries),
            18,
            msg=f"Group detail exceeded query budget: {len(queries)}",
        )
