from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Basic profile info
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    website = models.URLField(max_length=200, blank=True)

    # Content tracking (these will be updated by signals)
    total_articles = models.PositiveIntegerField(default=0)
    total_images = models.PositiveIntegerField(default=0)
    total_videos = models.PositiveIntegerField(default=0)

    # Engagement metrics
    total_views = models.PositiveIntegerField(default=0)
    total_likes = models.PositiveIntegerField(default=0)
    total_comments = models.PositiveIntegerField(default=0)

    # For future payment features
    content_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_email = models.EmailField(blank=True, null=True)

    # Additional fields
    joined_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def get_absolute_url(self):
        return reverse('profile', kwargs={'username': self.user.username})

    def update_content_counts(self):
        """Update the counts of user-created content"""
        self.total_articles = self.user.articles.count()  # Changed from article_set
        self.total_images = self.user.ai_images.count()   # Changed from aiimage_set
        self.total_videos = self.user.ai_videos.count()   # Changed from aivideo_set
        self.save()

# Signal to create user profile when a new user is created
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # Ensure profile exists for existing users
        profile, created = UserProfile.objects.get_or_create(user=instance)
        if not created:
            # Only save if we didn't just create it
            profile.save()

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class EarningsRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='earnings')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: ${self.amount} - {self.description[:20]}..."

class StripeAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='stripe_account')
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    charges_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    connected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Stripe Account"

class Payout(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payout_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}: ${self.amount} - {self.status}"
