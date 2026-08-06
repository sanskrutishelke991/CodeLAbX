from django.contrib import admin

from .models import Test, TestAttempt

admin.site.register(Test)
admin.site.register(TestAttempt)
