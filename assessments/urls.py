from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    path('', views.quiz_list, name='quiz_list'),
    path('create/', views.create_test, name='create'),
    path('api/generate/', views.generate_test_questions, name='generate'),
    path('take/<int:test_id>/', views.take_test, name='take'),
    path('api/submit/<int:test_id>/', views.submit_test, name='submit'),
    path('result/<int:test_id>/', views.test_result, name='result'),
]
