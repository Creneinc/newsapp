from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Article(models.Model):
    CATEGORY_CHOICES = [
        ("General", "General"),
        ("Tech", "Tech"),
        ("World", "World"),
        ("Business", "Business"),
        ("Politics", "Politics"),
        ("Sports", "Sports"),
        ("Entertainment", "Entertainment"),
        ("Health", "Health"),
        ("Science", "Science"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="articles")
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default="General")
    body = models.TextField()
    image = models.ImageField(upload_to='article_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Auto-updates on edits

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']  # Optional, if you want to sort articles by created_at in descending order


class Comment(models.Model):
    article = models.ForeignKey(Article, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.user.username} on {self.article.title}'

    class Meta:
        ordering = ['created_at']  # Order comments by creation date
