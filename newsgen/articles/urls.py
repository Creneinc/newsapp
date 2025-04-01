from django.urls import path
from .views import article_list, new_article, edit_article, delete_article, article_detail
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', article_list, name='article_list'),
    path('new/', new_article, name='new_article'),
    path('<int:pk>/', article_detail, name='article_detail'),  # ✅ New route for article details
    path('<int:pk>/edit/', edit_article, name='edit_article'),
    path('<int:pk>/delete/', delete_article, name='delete_article'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
