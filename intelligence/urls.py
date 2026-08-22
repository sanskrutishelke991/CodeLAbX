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
]
