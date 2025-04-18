from django.contrib import admin
from .models import Article, SiteSettings

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'view_count', 'likes', 'moderation_status', 'is_trending')
    list_editable = ('view_count', 'likes', 'moderation_status', 'is_trending')
    list_filter = ('category', 'moderation_status', 'is_trending')
    search_fields = ('title',)

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['auto_approve_articles', 'auto_approve_images', 'auto_approve_videos']
