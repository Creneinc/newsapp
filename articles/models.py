from django.db import models
from django.contrib.auth.models import User

class Article(models.Model):
    CATEGORY_CHOICES = [
        ("General", "General"),
        ("Tech", "Tech"),
        ("World", "World"),
        ("Business", "Business"),
        ("Politics", "Politics"),
        ("Sports", "Sports"),
        ("Entertainment", "Entertainment"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="articles")
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default="General")
    body = models.TextField()
    image = models.ImageField(upload_to='article_images/', max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, default="pending")  # e.g., "pending", "in_progress", "completed"

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']


class AIImage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_images")
    title = models.CharField(max_length=255, blank=True, null=True)  # <-- changed here
    image = models.ImageField(upload_to='ai_images/')
    prompt_used = models.TextField(blank=True, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or "Untitled AI Image"


class AIVideo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_videos", null=True)  # Add `null=True`
    title = models.CharField(max_length=255, blank=True, null=True)
    video = models.FileField(upload_to='ai_videos/', max_length=500)
    prompt_used = models.TextField(blank=True, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or "Untitled AI Video"


class Comment(models.Model):
    article = models.ForeignKey(Article, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.user.username} on {self.article.title}'

    class Meta:
        ordering = ['created_at']
