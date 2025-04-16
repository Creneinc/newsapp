from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('user/<str:username>/', views.public_profile, name='public_profile'),
    path('register/', views.register, name='register'),

    path('earnings/', views.earnings_dashboard, name='earnings'),
    path('connect-stripe/', views.connect_stripe, name='connect_stripe'),
    path('stripe-callback/', views.stripe_callback, name='stripe_callback'),
]
