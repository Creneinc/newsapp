# tasks.py
from celery import shared_task
import requests
import logging
from django.conf import settings  # Make sure to import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
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
