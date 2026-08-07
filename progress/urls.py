from django.urls import path
from . import views

app_name = 'progress'

urlpatterns = [
    path('', views.redirect_to_achievements, name='index'),
    path('achievements/', views.achievements, name='achievements'),
    path('badge/<int:badge_id>/', views.badge_detail, name='badge_detail'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('analytics/', views.analytics, name='analytics'),
    path('analytics/export.csv', views.analytics_export, name='analytics_export'),
]
