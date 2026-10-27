from django.contrib import admin

from .models import Bookmark, Note

admin.site.register(Note)
admin.site.register(Bookmark)
