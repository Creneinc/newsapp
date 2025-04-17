from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from articles.views import signup_view
from articles.models import get_category_dict  # ✅ Clean safe import

CATEGORIES = get_category_dict()  # ✅ No circular import

auth_patterns = [
    path('login/',
         auth_views.LoginView.as_view(
             extra_context={'categories': CATEGORIES}
         ),
         name='login'),
    # Add other auth views as needed
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('articles.urls')),
    path('accounts/', include(auth_patterns)),
    path('signup/', signup_view, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/', http_method_names=['get', 'post']), name='logout'),
    path('users/', include('users.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
