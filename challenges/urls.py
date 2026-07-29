from django.urls import path
from . import views

app_name = 'challenges'

urlpatterns = [
    path('', views.challenge_dashboard, name='dashboard'),
    path('attempt/<int:challenge_id>/', views.challenge_attempt, name='attempt'),
    path('submit/<int:challenge_id>/', views.challenge_submit, name='submit'),
    path('result/<int:challenge_id>/', views.challenge_result, name='result'),
    path('history/', views.challenge_history, name='history'),
]