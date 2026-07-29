from django.urls import path
from . import views

app_name = 'learning'

urlpatterns = [
    path('roadmaps/', views.roadmap_list, name='roadmaps'),
    path('roadmaps/create/', views.roadmap_create, name='roadmap_create'),
    path('roadmaps/<int:roadmap_id>/', views.roadmap_detail, name='roadmap_detail'),
    path('roadmaps/<int:roadmap_id>/day/<int:day_number>/', views.day_detail, name='day_detail'),
    
    
    path('roadmaps/<int:roadmap_id>/day/<int:day_number>/generate/', views.generate_day_content, name='generate_content'),
    path('roadmaps/<int:roadmap_id>/day/<int:day_number>/complete/', views.mark_day_complete, name='mark_complete'),
]