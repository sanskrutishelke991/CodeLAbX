from django.urls import path
from . import views

app_name = 'ai_tools'

urlpatterns = [
    path('chat/sessions/', views.chat_sessions_page, name='chat_sessions_page'),
    path('', views.ai_home, name='home'),
    
    # Chat
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/history/', views.chat_history, name='chat_history'),
    path('chat/session/<int:session_id>/', views.chat_get_session, name='chat_session'),
    path('chat/session/<int:session_id>/delete/', views.chat_delete_session, name='chat_delete'),
    path('chat/new/', views.chat_new_session, name='chat_new'),
    
    # Image Analysis
    path('image/', views.image_analyzer, name='image_analyzer'),
    path('image/<int:analysis_id>/', views.image_result, name='image_result'),
    path('image/history/', views.image_history, name='image_history'),
    path('image/<int:analysis_id>/delete/', views.image_delete, name='image_delete'),
]