from django.contrib import admin
from django.urls import path, include
from articles.views import signup_view
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('articles.urls')),  # Include article-related URLs (article list, details, etc.)
    path('accounts/', include('django.contrib.auth.urls')),  # Includes login, logout, password reset routes
    path('signup/', signup_view, name='signup'),  # Custom signup page
    path('logout/', auth_views.LogoutView.as_view(next_page='/', http_method_names=['get', 'post']), name='logout'),
]

# Add this for development environments only (media files serving)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
