from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.http import JsonResponse
from django.conf import settings

from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
from .models import UserProfile, StripeAccount, Payout, EarningsRecord
from articles.models import Article, AIImage, AIVideo

import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})

@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your profile has been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    # Get user's content
    articles = Article.objects.filter(user=request.user).order_by('-created_at')[:5]
    images = AIImage.objects.filter(user=request.user).order_by('-generated_at')[:5]
    videos = AIVideo.objects.filter(user=request.user).order_by('-generated_at')[:5]

    # Update the profile counts
    request.user.profile.update_content_counts()

    # Import the categories from articles app
    from articles.views import CATEGORIES

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'articles': articles,
        'images': images,
        'videos': videos,
        'categories': CATEGORIES,  # Add categories to context
    }

    return render(request, 'users/profile.html', context)

def public_profile(request, username):
    user = get_object_or_404(User, username=username)

    # Get user's content
    articles = Article.objects.filter(user=user).order_by('-created_at')[:10]
    images = AIImage.objects.filter(user=user).order_by('-generated_at')[:6]
    videos = AIVideo.objects.filter(user=user).order_by('-generated_at')[:4]

    # Import the categories from articles app
    from articles.views import CATEGORIES

    context = {
        'profile_user': user,
        'articles': articles,
        'images': images,
        'videos': videos,
        'categories': CATEGORIES,  # Add categories to context
    }

    return render(request, 'users/public_profile.html', context)

@login_required
def dashboard(request):
    """A comprehensive dashboard with all user content and stats"""

    # Get all user content
    articles = Article.objects.filter(user=request.user).order_by('-created_at')
    images = AIImage.objects.filter(user=request.user).order_by('-generated_at')
    videos = AIVideo.objects.filter(user=request.user).order_by('-generated_at')

    # Update the profile counts
    request.user.profile.update_content_counts()

    # Import the categories from articles app
    from articles.views import CATEGORIES

    context = {
        'articles': articles,
        'images': images,
        'videos': videos,
        'article_count': request.user.profile.total_articles,
        'image_count': request.user.profile.total_images,
        'video_count': request.user.profile.total_videos,
        'total_content': request.user.profile.total_articles + request.user.profile.total_images + request.user.profile.total_videos,
        'categories': CATEGORIES,  # Add categories to context
    }

    return render(request, 'users/dashboard.html', context)

@login_required
def connect_stripe(request):
    # URL the user will be redirected to after connecting their Stripe account
    redirect_uri = request.build_absolute_uri(reverse('stripe_callback'))

    # Generate a Stripe OAuth link
    oauth_link = f"https://connect.stripe.com/oauth/authorize?response_type=code&client_id={settings.STRIPE_CONNECT_CLIENT_ID}&scope=read_write&redirect_uri={redirect_uri}"

    return redirect(oauth_link)

@login_required
def stripe_callback(request):
    code = request.GET.get('code')

    if not code:
        messages.error(request, "Connection to Stripe failed. Please try again.")
        return redirect('earnings')

    try:
        # Exchange the authorization code for an access token
        response = stripe.OAuth.token(
            grant_type='authorization_code',
            code=code,
        )

        # Save the connected account ID
        stripe_account_id = response['stripe_user_id']

        # Get account details to check if charges and payouts are enabled
        account = stripe.Account.retrieve(stripe_account_id)

        # Create or update the Stripe account record
        stripe_account, created = StripeAccount.objects.update_or_create(
            user=request.user,
            defaults={
                'stripe_account_id': stripe_account_id,
                'charges_enabled': account.charges_enabled,
                'payouts_enabled': account.payouts_enabled,
            }
        )

        messages.success(request, "Successfully connected your Stripe account!")
    except Exception as e:
        messages.error(request, f"Error connecting to Stripe: {str(e)}")

    return redirect('earnings')

@login_required
def earnings_dashboard(request):
    # Get earnings records for the current user
    earnings = EarningsRecord.objects.filter(user=request.user).order_by('-timestamp')

    # Calculate total earnings
    total_earnings = sum(record.amount for record in earnings)

    # Get payout history
    payouts = Payout.objects.filter(user=request.user).order_by('-created_at')

    # Calculate pending balance (earnings minus payouts)
    total_paid = sum(payout.amount for payout in payouts if payout.status == 'paid')
    pending_balance = total_earnings - total_paid

    # Check if user has connected Stripe account
    try:
        stripe_account = StripeAccount.objects.get(user=request.user)
        is_stripe_connected = bool(stripe_account.stripe_account_id)
    except StripeAccount.DoesNotExist:
        stripe_account = None
        is_stripe_connected = False

    # Import categories from articles app (add this line)
    from articles.views import CATEGORIES

    context = {
        'earnings': earnings,
        'payouts': payouts,
        'total_earnings': total_earnings,
        'pending_balance': pending_balance,
        'is_stripe_connected': is_stripe_connected,
        'stripe_account': stripe_account,
        'categories': CATEGORIES,  # Add this line to include categories
    }

    return render(request, 'users/earnings.html', context)
