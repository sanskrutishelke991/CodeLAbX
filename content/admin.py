from django.contrib import admin

from .models import UserVideoProgress, Video, VideoCategory

admin.site.register(VideoCategory)
admin.site.register(Video)
admin.site.register(UserVideoProgress)
