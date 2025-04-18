from django.urls import path
from .views import article_list, new_article, edit_article, delete_article, article_detail, home_view, stream_article_generation
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth import views as auth_views
from . import views
from articles.views import search_results, ai_image_detail, ai_video_detail, signup_view
from articles import views

urlpatterns = [
    path('', home_view, name='home'),  # This is the main page
    path('articles/', article_list, name='article_list'),  # All/filter/category views
    path('signup/', signup_view, name='signup'),
    path('articles/<int:pk>-<slug:slug>/', article_detail, name='article_detail'),
    path('articles/<int:pk>-<slug:slug>/edit/', edit_article, name='edit_article'),
    path('articles/<int:pk>-<slug:slug>/delete/', delete_article, name='delete_article'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('create/image/', views.upload_image, name='upload_image'),
    path('create/video/', views.upload_video, name='upload_video'),
    path('ai-images/', views.ai_image_gallery, name='ai_image_gallery'),
    path('ai-videos/', views.ai_video_gallery, name='ai_video_gallery'),
    path('search/', search_results, name='search_results'),
    path('ai-images/<int:pk>-<slug:slug>/', ai_image_detail, name='ai_image_detail'),
    path('ai-videos/<int:pk>-<slug:slug>/', ai_video_detail, name='ai_video_detail'),
    path('ai-images/delete/<int:pk>/', views.delete_ai_image, name='delete_ai_image'),
    path('ai-videos/delete/<int:pk>/', views.delete_ai_video, name='delete_ai_video'),
    path('check-article-status/', views.check_article_status, name='check_article_status'),
    path('ai-images/<int:pk>-<slug:slug>/comment/', views.add_image_comment, name='add_image_comment'),
    path('ai-videos/<int:pk>-<slug:slug>/comment/', views.add_video_comment, name='add_video_comment'),
    path('article/<int:pk>-<slug:slug>/approve/', views.approve_article, name='approve_article'),
    path('article/<int:pk>-<slug:slug>/reject/', views.reject_article, name='reject_article'),
    path('article/<int:pk>/like/', views.like_article, name='like_article'),

    path('create/article/', views.new_article, name='new_article'),  # This is for standard form
    path('create/article/ajax/', views.create_article, name='create_article'),  # This is for AJAX requests
    path('create/article/stream/', views.stream_article_generation, name='stream_article'),
    path('stream-groq/', stream_article_generation, name='stream_article_generation'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
