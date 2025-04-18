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
        # To be added in the future
        # ('news', 'News'),
        # ('tech', 'Technology'),
        # ('science', 'Science'),
        # ('health', 'Health'),
    ]

    MODERATION_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
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

    # New fields for content moderation and popularity tracking
    moderation_status = models.CharField(
        max_length=10,
        choices=MODERATION_CHOICES,
        default='pending'
    )
    is_trending = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)

    # Optional: add video field for AI Video content
    video = models.FileField(upload_to='article_videos/', max_length=255, null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']

def get_category_dict():
    return dict(Article.CATEGORY_CHOICES)

class Comment(models.Model):
    article = models.ForeignKey(Article, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.user.username} on {self.article.title}'

    class Meta:
        ordering = ['created_at']

class ArticleView(models.Model):
    # Change the related_name from 'views' to 'article_views'
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='article_views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='article_views')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        # Optional - prevents the same user or IP from inflating view count within a timeframe
        unique_together = [['article', 'user', 'ip_address', 'timestamp']]
        indexes = [
            models.Index(fields=['timestamp']),  # For efficient date range queries
            models.Index(fields=['article', 'timestamp']),  # For article-specific date queries
        ]

    def __str__(self):
        return f"View of {self.article.title} at {self.timestamp}"
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


class ImageComment(models.Model):
    image = models.ForeignKey(AIImage, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.image.title}"

class VideoComment(models.Model):
    video = models.ForeignKey(AIVideo, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.video.title}"

def get_category_dict():
    return dict(Article.CATEGORY_CHOICES)
