from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from articles.models import Article, AIImage, AIVideo

@receiver(post_save, sender=Article)
def update_profile_on_article_change(sender, instance, **kwargs):
    """Update user profile stats when an article is created or updated"""
    if hasattr(instance.user, 'profile'):
        instance.user.profile.update_content_counts()

@receiver(post_delete, sender=Article)
def update_profile_on_article_delete(sender, instance, **kwargs):
    """Update user profile stats when an article is deleted"""
    if hasattr(instance.user, 'profile'):
        instance.user.profile.update_content_counts()

@receiver(post_save, sender=AIImage)
def update_profile_on_image_change(sender, instance, **kwargs):
    """Update user profile stats when an image is created or updated"""
    if hasattr(instance.user, 'profile'):
        instance.user.profile.update_content_counts()

@receiver(post_delete, sender=AIImage)
def update_profile_on_image_delete(sender, instance, **kwargs):
    """Update user profile stats when an image is deleted"""
    if hasattr(instance.user, 'profile'):
        instance.user.profile.update_content_counts()

@receiver(post_save, sender=AIVideo)
def update_profile_on_video_change(sender, instance, **kwargs):
    """Update user profile stats when a video is created or updated"""
    if hasattr(instance.user, 'profile'):
        instance.user.profile.update_content_counts()

@receiver(post_delete, sender=AIVideo)
def update_profile_on_video_delete(sender, instance, **kwargs):
    """Update user profile stats when a video is deleted"""
    if hasattr(instance.user, 'profile'):
        instance.user.profile.update_content_counts()
