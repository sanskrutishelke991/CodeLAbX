from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("", views.group_list, name="groups"),
    path("create/", views.group_create, name="group_create"),
    path("join/<uuid:token>/", views.join_invite, name="join_invite"),
    path("groups/<int:group_id>/", views.group_detail, name="group_detail"),
    path("groups/<int:group_id>/invite/", views.invite_create, name="invite_create"),
    path("groups/<int:group_id>/leave/", views.group_leave, name="group_leave"),
    path("groups/<int:group_id>/archive/", views.group_archive, name="group_archive"),
    path("groups/<int:group_id>/roadmaps/share/", views.roadmap_share, name="roadmap_share"),
    path("groups/<int:group_id>/roadmaps/<int:share_id>/unshare/", views.roadmap_unshare, name="roadmap_unshare"),
    path("groups/<int:group_id>/roadmaps/<int:roadmap_id>/", views.shared_roadmap, name="shared_roadmap"),
    path("groups/<int:group_id>/roadmaps/<int:roadmap_id>/days/<int:day_number>/", views.shared_day, name="shared_day"),
    path("groups/<int:group_id>/days/<int:day_id>/comments/", views.group_day_comment_create, name="group_day_comment_create"),
    path("day-comments/<int:comment_id>/delete/", views.day_comment_delete, name="day_comment_delete"),
    path("days/<int:day_id>/comments/", views.personal_day_comment_create, name="personal_day_comment_create"),
    path("groups/<int:group_id>/threads/create/", views.thread_create, name="thread_create"),
    path("groups/<int:group_id>/threads/<int:thread_id>/", views.thread_detail, name="thread_detail"),
    path("groups/<int:group_id>/threads/<int:thread_id>/reply/", views.post_create, name="post_create"),
    path("groups/<int:group_id>/posts/<int:post_id>/delete/", views.post_delete, name="post_delete"),
    path("groups/<int:group_id>/report/<str:target_type>/<int:target_id>/", views.content_report, name="content_report"),
    path("groups/<int:group_id>/moderation/", views.moderation_reports, name="moderation_reports"),
    path("groups/<int:group_id>/moderation/<int:report_id>/<str:resolution>/", views.moderation_action, name="moderation_action"),
    path("groups/<int:group_id>/members/<int:membership_id>/<str:action>/", views.member_action, name="member_action"),
    path("users/<int:user_id>/<str:action>/", views.user_block_action, name="user_block_action"),
]
