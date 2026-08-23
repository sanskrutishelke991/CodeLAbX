from django.urls import path

from . import views

app_name = "intelligence"

urlpatterns = [
    path("", views.home, name="home"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("diagnostic/", views.diagnostic, name="diagnostic"),
    path("diagnostic/submit/", views.diagnostic_submit, name="diagnostic_submit"),
    path("dna/", views.dna, name="dna"),
    path("baseline/", views.dna, name="baseline"),
    path("evidence/", views.evidence_explorer, name="evidence"),
    path("passport/", views.skill_passport, name="passport"),
    path("sharing/", views.sharing_dashboard, name="sharing"),
    path(
        "sharing/passport/create/",
        views.create_passport_share,
        name="create_passport_share",
    ),
    path(
        "sharing/roadmap/<int:roadmap_id>/create/",
        views.create_roadmap_share,
        name="create_roadmap_share",
    ),
    path(
        "sharing/<int:share_id>/refresh/",
        views.refresh_share,
        name="refresh_share",
    ),
    path(
        "sharing/<int:share_id>/revoke/",
        views.revoke_share,
        name="revoke_share",
    ),
    path(
        "shared/<uuid:public_id>/",
        views.public_share,
        name="public_share",
    ),
    path("retention/", views.retention_center, name="retention"),
    path(
        "retention/<int:skill_id>/mission/",
        views.create_refresh_mission,
        name="create_refresh_mission",
    ),
    path(
        "recommendations/recalculate/",
        views.recalculate_recommendation,
        name="recalculate_recommendation",
    ),
    path("routes/", views.adaptive_routes, name="adaptive_routes"),
    path(
        "routes/propose/",
        views.create_route_proposal,
        name="create_route_proposal",
    ),
    path(
        "routes/<int:roadmap_id>/",
        views.adaptive_route_detail,
        name="adaptive_route_detail",
    ),
    path(
        "routes/<int:roadmap_id>/initialize/",
        views.initialize_route,
        name="initialize_route",
    ),
    path(
        "routes/<int:roadmap_id>/revisions/<int:revision_id>/accept/",
        views.revision_action,
        {"action": "accept"},
        name="accept_revision",
    ),
    path(
        "routes/<int:roadmap_id>/revisions/<int:revision_id>/reject/",
        views.revision_action,
        {"action": "reject"},
        name="reject_revision",
    ),
    path(
        "routes/<int:roadmap_id>/revisions/<int:revision_id>/postpone/",
        views.revision_action,
        {"action": "postpone"},
        name="postpone_revision",
    ),
    path(
        "routes/<int:roadmap_id>/revisions/<int:revision_id>/resume/",
        views.revision_action,
        {"action": "resume"},
        name="resume_revision",
    ),
    path(
        "routes/<int:roadmap_id>/revisions/<int:revision_id>/restore/",
        views.restore_route_revision,
        name="restore_route_revision",
    ),
    path(
        "routes/<int:roadmap_id>/nodes/<int:node_id>/toggle-pin/",
        views.toggle_route_node_lock,
        name="toggle_route_node_lock",
    ),
    path("tutor/", views.tutor_home, name="tutor_home"),
    path(
        "tutor/preferences/",
        views.tutor_preferences,
        name="tutor_preferences",
    ),
    path("tutor/memory/", views.tutor_memory, name="tutor_memory"),
    path(
        "tutor/memory/add/",
        views.tutor_memory_add,
        name="tutor_memory_add",
    ),
    path(
        "tutor/memory/<int:memory_id>/update/",
        views.tutor_memory_update,
        name="tutor_memory_update",
    ),
    path(
        "tutor/memory/<int:memory_id>/delete/",
        views.tutor_memory_delete,
        name="tutor_memory_delete",
    ),
    path(
        "tutor/memory/forget-all/",
        views.tutor_memory_forget_all,
        name="tutor_memory_forget_all",
    ),
    path("tutor/feedback/", views.tutor_feedback, name="tutor_feedback"),
]
