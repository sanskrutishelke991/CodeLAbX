from django.contrib import admin

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


class MembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    readonly_fields = ("joined_at",)


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "max_members", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "owner__username")
    inlines = [MembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("group__name", "user__username")


@admin.register(GroupInvite)
class GroupInviteAdmin(admin.ModelAdmin):
    list_display = ("group", "created_by", "use_count", "max_uses", "is_active", "expires_at")
    list_filter = ("is_active",)
    readonly_fields = ("token", "created_at", "use_count")


@admin.register(GroupRoadmapShare)
class GroupRoadmapShareAdmin(admin.ModelAdmin):
    list_display = ("group", "roadmap", "shared_by", "created_at")
    search_fields = ("group__name", "roadmap__title", "shared_by__username")


@admin.register(DiscussionThread)
class DiscussionThreadAdmin(admin.ModelAdmin):
    list_display = ("title", "group", "author", "is_pinned", "is_locked", "is_hidden", "updated_at")
    list_filter = ("is_pinned", "is_locked", "is_hidden")
    search_fields = ("title", "body", "group__name", "author__username")


@admin.register(DiscussionPost)
class DiscussionPostAdmin(admin.ModelAdmin):
    list_display = ("thread", "author", "is_deleted", "is_hidden", "created_at")
    list_filter = ("is_deleted", "is_hidden")
    search_fields = ("body", "author__username", "thread__title")


@admin.register(DayComment)
class DayCommentAdmin(admin.ModelAdmin):
    list_display = ("day", "group", "author", "is_deleted", "is_hidden", "created_at")
    list_filter = ("is_deleted", "is_hidden")
    search_fields = ("body", "author__username", "day__title", "group__name")


@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")


@admin.register(CommunityReport)
class CommunityReportAdmin(admin.ModelAdmin):
    list_display = ("group", "reporter", "target_type", "target_id", "reason", "status", "created_at")
    list_filter = ("target_type", "reason", "status")
    search_fields = ("group__name", "reporter__username", "details")
    readonly_fields = [field.name for field in CommunityReport._meta.fields]
