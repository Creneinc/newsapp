from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    article_list, new_article, create_article, stream_article_generation,
    edit_article, delete_article, article_detail, home_view,
    upload_image, upload_video,
    ai_image_gallery, ai_video_gallery,
    ai_image_detail, ai_video_detail,
    delete_ai_image, delete_ai_video,
    like_content,
    check_article_status,
    approve_article, reject_article,
    add_image_comment, add_video_comment,
    signup_view,
    search_results,
)

urlpatterns = [
    # Home & Auth
    path('', home_view, name='home'),
    path('signup/', signup_view, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # Articles
    path('articles/', article_list, name='article_list'),
    path('articles/<int:pk>-<slug:slug>/', article_detail, name='article_detail'),
    path('articles/<int:pk>-<slug:slug>/edit/', edit_article, name='edit_article'),
    path('articles/<int:pk>-<slug:slug>/delete/', delete_article, name='delete_article'),
    path('article/<int:pk>-<slug:slug>/approve/', approve_article, name='approve_article'),
    path('article/<int:pk>-<slug:slug>/reject/', reject_article, name='reject_article'),

    # Like content functionality
    path('<str:content_type>/<int:pk>/like/', views.like_content, name='like_content'),

    # AI Article Creation
    path('create/article/', new_article, name='new_article'),
    path('create/article/ajax/', create_article, name='create_article'),
    path('create/article/stream/', views.stream_article_generation, name='stream_article_generation'),
    path('stream-groq/', stream_article_generation, name='stream_article_generation'),  # Consider removing if redundant
    path('check-article-status/', check_article_status, name='check_article_status'),

    # AI Images
    path('ai-images/', ai_image_gallery, name='ai_image_gallery'),
    path('ai-images/<int:pk>-<slug:slug>/', ai_image_detail, name='ai_image_detail'),
    path('ai-images/delete/<int:pk>/', delete_ai_image, name='delete_ai_image'),
    path('ai-images/<int:pk>-<slug:slug>/comment/', add_image_comment, name='add_image_comment'),

    # AI Videos
    path('ai-videos/', ai_video_gallery, name='ai_video_gallery'),
    path('ai-videos/<int:pk>-<slug:slug>/', ai_video_detail, name='ai_video_detail'),
    path('ai-videos/delete/<int:pk>/', delete_ai_video, name='delete_ai_video'),
    path('ai-videos/<int:pk>-<slug:slug>/comment/', add_video_comment, name='add_video_comment'),

    # AI Insights
    path('ai-insights/', views.ai_insights_page, name='ai_insights_page'),

    # Uploads
    path('create/image/', upload_image, name='upload_image'),
    path('create/video/', upload_video, name='upload_video'),

    # Search
    path('search/', search_results, name='search_results'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
