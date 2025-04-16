# tasks.py
from celery import shared_task
import requests
import logging
from django.conf import settings  # Make sure to import settings

from django.contrib.auth.models import User
from django.db.models import Count, Sum
from users.models import EarningsRecord
from articles.models import Article, Comment, AIImage, AIVideo
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=30, time_limit=600)
def generate_article_task(self, title, summary, category, article_id):
    try:
        # Prepare the prompt for the article generation
        prompt = f"Write a full news article in the '{category}' category.\n\nTitle: {title}\n"
        if summary:
            prompt += f"Summary: {summary}\n"
        prompt += "\nOnly write the body of the article. Do not include the title."

        # Send request to the Mistral API
        response = requests.post(
            f"{settings.OLLAMA_API_URL}/api/generate",  # Using environment variable for the API URL
            headers={"Content-Type": "application/json"},
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=None  # Timeout is removed to wait indefinitely
        )

        # Check if the response status is successful (200 OK)
        if response.status_code == 200:
            body = response.json().get("response", "").strip()
            if len(body) > 50:
                # Update the article's body if successful
                from articles.models import Article
                article = Article.objects.get(id=article_id)
                article.body = body
                article.status = "completed"
                article.save()
                return body
            else:
                raise ValueError("Generated content too short")
        else:
            # Raise an error if the response status is not 200
            raise Exception(f"Status {response.status_code}: {response.text}")

    except Exception as exc:
        logger.error(f"Article generation failed: {exc}")
        # Retry the task if it fails
        self.retry(exc=exc)

@shared_task
def calculate_earnings():
    """
    Calculate earnings for users based on their content performance
    This is a simplified example - you would need to adjust this based on your
    actual revenue streams and metrics
    """
    # Get the date range for this calculation (last day)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=1)

    # Calculate earnings for articles
    # Example: $0.01 per view
    article_views = Article.objects.filter(
        # Assuming you have a views tracking mechanism that logs timestamps
        views__timestamp__gte=start_date,
        views__timestamp__lt=end_date
    ).values('user').annotate(
        total_views=Count('views')
    )

    # Calculate earnings for images
    # Example: $0.005 per view
    image_views = AIImage.objects.filter(
        views__timestamp__gte=start_date,
        views__timestamp__lt=end_date
    ).values('user').annotate(
        total_views=Count('views')
    )

    # Calculate earnings for videos
    # Example: $0.02 per view
    video_views = AIVideo.objects.filter(
        views__timestamp__gte=start_date,
        views__timestamp__lt=end_date
    ).values('user').annotate(
        total_views=Count('views')
    )

    # Record earnings for each user
    for user_data in article_views:
        user_id = user_data['user']
        views = user_data['total_views']
        amount = views * 0.01  # $0.01 per view

        if amount > 0:
            user = User.objects.get(id=user_id)
            EarningsRecord.objects.create(
                user=user,
                amount=amount,
                description=f"Article views earnings ({views} views)"
            )

    # Similar process for images and videos
    # [code would be similar to above]

    return "Earnings calculation completed"

@shared_task
def process_payouts():
    """
    Process payouts to users with connected Stripe accounts
    Only pay out balances over a minimum threshold
    """
    import stripe
    from django.conf import settings
    from users.models import StripeAccount, Payout

    stripe.api_key = settings.STRIPE_SECRET_KEY
    min_payout_amount = 25.00  # $25 minimum payout

    # Get users with connected Stripe accounts and pending balances
    users_with_stripe = StripeAccount.objects.filter(
        payouts_enabled=True,
        stripe_account_id__isnull=False
    ).select_related('user')

    for stripe_account in users_with_stripe:
        user = stripe_account.user

        # Calculate pending balance
        total_earnings = EarningsRecord.objects.filter(user=user).aggregate(
            total=Sum('amount')
        )['total'] or 0

        total_paid = Payout.objects.filter(
            user=user,
            status='paid'
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        pending_balance = total_earnings - total_paid

        # Only process if pending balance is above threshold
        if pending_balance >= min_payout_amount:
            # Convert to cents for Stripe
            amount_cents = int(pending_balance * 100)

            try:
                # Create a transfer
                transfer = stripe.Transfer.create(
                    amount=amount_cents,
                    currency="usd",
                    destination=stripe_account.stripe_account_id,
                    description=f"Creator earnings payout for {user.username}"
                )

                # Record the payout
                Payout.objects.create(
                    user=user,
                    amount=pending_balance,
                    stripe_payout_id=transfer.id,
                    status='paid',
                    completed_at=timezone.now()
                )

            except Exception as e:
                # Log the error and create a failed payout record
                print(f"Payout failed for {user.username}: {str(e)}")
                Payout.objects.create(
                    user=user,
                    amount=pending_balance,
                    status='failed',
                    completed_at=timezone.now()
                )

    return "Payouts processing completed"
