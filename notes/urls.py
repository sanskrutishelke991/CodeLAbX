from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    # Notes
    path('', views.notes_list, name='list'),
    path('create/', views.note_create, name='create'),
    path('<int:note_id>/edit/', views.note_edit, name='edit'),
    path('<int:note_id>/delete/', views.note_delete, name='delete'),
    path('<int:note_id>/pin/', views.note_pin_toggle, name='pin_toggle'),
    path('<int:note_id>/export/', views.note_export, name='export'),
    
    # Bookmarks
    path('bookmarks/', views.bookmarks_list, name='bookmarks'),
    path('bookmarks/add/', views.bookmark_add, name='bookmark_add'),
    path('bookmarks/<int:bookmark_id>/delete/', views.bookmark_delete, name='bookmark_delete'),
]