from django.urls import path

from . import views

app_name = "intelligence"

urlpatterns = [
    path("", views.home, name="home"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("diagnostic/", views.diagnostic, name="diagnostic"),
    path("diagnostic/submit/", views.diagnostic_submit, name="diagnostic_submit"),
    path("baseline/", views.baseline, name="baseline"),
]
