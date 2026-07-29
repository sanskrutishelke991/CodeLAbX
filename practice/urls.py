from django.urls import path
from . import views

app_name = 'practice'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('home/', views.task_list, name='home'),
    path('examiner/', views.code_examiner, name='examiner'),
    path('api/check-code/', views.check_code, name='check_code'),
    path('api/generate-problem/', views.generate_problem, name='generate_problem'),
]