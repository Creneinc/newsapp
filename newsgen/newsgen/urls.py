from django.contrib import admin
from django.urls import path, include
from articles.views import signup_view, CATEGORIES  # Import CATEGORIES
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

# Define auth paths explicitly with categories context
auth_patterns = [
    path('login/',
        auth_views.LoginView.as_view(
            extra_context={'categories': CATEGORIES}
        ),
        name='login'),
    # Add other auth views you need
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('articles.urls')),
    path('accounts/', include(auth_patterns)),  # Use our custom auth patterns
    path('signup/', signup_view, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/', http_method_names=['get', 'post']), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
