from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    path('', views.library, name='library'),
    path('video/<int:video_id>/', views.video_detail, name='video_detail'),
    path('video/<int:video_id>/watched/', views.video_mark_watched, name='mark_watched'),
    path('video/<int:video_id>/favorite/', views.video_toggle_favorite, name='toggle_favorite'),
    path('my-videos/', views.my_videos, name='my_videos'),
]