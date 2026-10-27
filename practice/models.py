import hashlib

from django.conf import settings
from django.db import models


class CodeReview(models.Model):
    """One rewarded review per user and normalized code hash."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="code_reviews",
    )
    language = models.CharField(max_length=30)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "code_hash"],
                name="unique_user_code_review_hash",
            )
        ]
        indexes = [models.Index(fields=["user", "created_at"])]

    @staticmethod
    def hash_code(language, code):
        value = f"{language}\0{code}".encode("utf-8")
        return hashlib.sha256(value).hexdigest()

    def __str__(self):
        return f"{self.user.username}: {self.language} review"
