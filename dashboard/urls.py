from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('', views.home, name='home'),
]
