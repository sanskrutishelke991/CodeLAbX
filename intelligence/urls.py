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
]
