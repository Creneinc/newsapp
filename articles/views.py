from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from articles.models import get_category_dict
from .models import Article, Comment, AIImage, AIVideo, ImageComment, VideoComment, get_category_dict
from .forms import ArticleForm, CommentForm
from articles.tasks import generate_article_task
from django.template.loader import render_to_string
from celery.result import AsyncResult
from uuid import uuid4
import requests
import json
import logging
import time
import os
import time



logger = logging.getLogger(__name__)

CATEGORIES = get_category_dict()

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

# 🔐 User Signup
def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('article_list')
    else:
        form = UserCreationForm()

    return render(request, 'registration/signup.html', {
        'form': form,
        'categories': CATEGORIES
    })

# 🧠 Create with AI form
@login_required
def new_article(request):
    form = ArticleForm()
    return render(request, 'articles/new_article.html', {
        'form': form,
        'categories': CATEGORIES,
    })
def generate_article(title, summary, category):
    prompt = f"Write a full news article in the '{category}' category based on the following details.\n\nTitle: {title}\n"
    if summary:
        prompt += f"Summary: {summary}\n"
    prompt += "\nOnly write the body of the article. Do not include the title."

    try:
        logger.info("Sending request to Mistral API...")

        response = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            headers={"Content-Type": "application/json"},
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False
            },
            timeout=600  # Increase timeout if necessary
        )

        # Log the response content to check its structure
        logger.info(f"Mistral API response: {response.text}")

        if response.status_code == 200:
            try:
                result = response.json()  # Try to parse the JSON response
                article_content = result.get("response", "")
                if len(article_content.strip()) > 50:
                    return article_content.strip()
                else:
                    logger.warning("Mistral returned content that was too short.")
            except ValueError as e:
                logger.error(f"Error parsing Mistral response as JSON: {e}")
                logger.error(f"Raw response: {response.text}")
                return "Error: Unable to process the AI response."

        else:
            logger.error(f"Mistral API error: {response.status_code} - {response.text}")
            return f"Error: {response.status_code} - {response.text}"

    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Mistral failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during Mistral call: {e}")

    return f"""
    {category}

    {summary}
    """.strip()


# 📝 AJAX Article Creation
@login_required
def create_article(request):
    if request.method == 'POST':
        try:
            logger.info("Received AJAX POST request for article creation.")
            logger.info(f"FILES: {request.FILES}")
            logger.info(f"POST data: {request.POST}")

            title = request.POST.get('title', '').strip()
            summary = request.POST.get('summary', '').strip()
            category = request.POST.get('category', 'General').strip()

            if not title:
                logger.warning("Missing title in request.")
                return JsonResponse({'status': 'error', 'message': 'Title is required!'}, status=400)

            # First, create the article with a "generating" status
            article = Article.objects.create(
                user=request.user,
                title=title,
                summary=summary,
                category=category,
                body="⏳ Generating article..."
            )

            try:
                logger.info("Sending request to Mistral API...")

                # Create the prompt
                prompt = f"Write a full news article in the '{category}' category based on the following details.\n\nTitle: {title}\n"
                if summary:
                    prompt += f"Summary: {summary}\n"
                prompt += "\nOnly write the body of the article. Do not include the title."

                # OPTION 1: Use stream=False (simpler approach)
                response = requests.post(
                    f"{OLLAMA_API_URL}/api/generate",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": "mistral",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=600
                )

                logger.info(f"Mistral API responded with status code {response.status_code}")

                if response.status_code == 200:
                    try:
                        result = response.json()
                        article_content = result.get("response", "")

                        # Update the article with the generated content
                        if len(article_content.strip()) > 50:
                            article.body = article_content.strip()
                            article.save()
                            return JsonResponse({
                                'status': 'success',
                                'message': 'Article created successfully!',
                                'article_id': article.id
                            })
                        else:
                            logger.warning("Mistral returned content that was too short.")
                            article.body = f"Could not generate article content. Here's your summary:\n\n{summary}"
                            article.save()
                    except ValueError as e:
                        logger.error(f"Error parsing Mistral response as JSON: {e}")
                        logger.error(f"Raw response: {response.text}")
                        article.body = f"Error processing AI response: {str(e)}\n\n{summary}"
                        article.save()
                else:
                    logger.error(f"Mistral API error: {response.status_code} - {response.text}")
                    article.body = f"Error generating content. Status code: {response.status_code}"
                    article.save()

            except requests.exceptions.RequestException as e:
                logger.error(f"Request to Mistral failed: {e}")
                article.body = f"Error connecting to AI service: {str(e)}\n\n{summary}"
                article.save()
            except Exception as e:
                logger.error(f"Unexpected error during Mistral call: {e}")
                article.body = f"Unexpected error: {str(e)}\n\n{summary}"
                article.save()

            # Even if we had an error, we created an article, so return success
            return JsonResponse({
                'status': 'success',
                'message': 'Article created (with potential errors).',
                'article_id': article.id
            })

        except Exception as e:
            logger.error(f"Unexpected error in create_article: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'An unexpected error occurred. Please try again.'
            }, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

# Check status of article generation task via AJAX
@login_required
def check_article_status(request):
    task_id = request.session.get('article_task_id')
    article_id = request.session.get('article_id')

    if not task_id or not article_id:
        return JsonResponse({'status': 'error'})

    result = AsyncResult(task_id)

    if result.ready():
        try:
            article = Article.objects.get(pk=article_id)
            if article.body and "⏳" not in article.body:
                return JsonResponse({
                    'status': 'done',
                    'redirect_url': f"/articles/{article.pk}/"
                })
        except Article.DoesNotExist:
            pass

    return JsonResponse({'status': 'pending'})

# Trending algorithm (time-decayed)
def get_trending_articles():
    recent_articles = Article.objects.filter(
        moderation_status='approved',
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    )
    for article in recent_articles:
        age_hours = (timezone.now() - article.created_at).total_seconds() / 3600
        article.trending_score = (article.view_count + article.likes * 3) / (1 + age_hours)
    sorted_articles = sorted(recent_articles, key=lambda a: a.trending_score, reverse=True)
    return sorted_articles[:4]


def article_list(request):
    # Get query parameters
    category = request.GET.get('category')

    # Determine if this is the main page (no category filter)
    is_main_page = category is None

    # Your existing view code...
    articles = Article.objects.all().order_by('-created_at')

    # Apply category filter if provided
    if category:
        if ',' in category:
            categories = category.split(',')
            articles = articles.filter(category__in=categories)
        else:
            articles = articles.filter(category=category)

    # Get popular articles
    popular_articles = Article.objects.filter(
        moderation_status='approved'
    ).order_by('-view_count', '-created_at')[:4]

    # Get recommended articles
    if request.user.is_authenticated:
        recommended_articles = Article.objects.filter(
            moderation_status='approved'
        ).exclude(id__in=[a.id for a in popular_articles]).order_by('-created_at')[:4]
    else:
        recommended_articles = []

    # Get AI content
    ai_images = AIImage.objects.all().order_by('-generated_at')[:1]
    ai_videos = AIVideo.objects.all().order_by('-generated_at')[:1]

    context = {
        'articles': articles,
        'popular_articles': popular_articles,
        'recommended_articles': recommended_articles,
        'ai_images': ai_images,
        'ai_videos': ai_videos,
        'categories': CATEGORIES,
        'is_main_page': is_main_page,  # Add this flag
    }

    return render(request, 'articles/article_list.html', context)

# 🔎 Article Detail + Comments
def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)

    # Increment view count
    article.view_count += 1
    article.save(update_fields=['view_count'])

    comments = article.comments.all()

    if request.method == 'POST' and request.user.is_authenticated:
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = article
            comment.user = request.user
            comment.save()
            messages.success(request, "Your comment has been added!")
            return redirect('article_detail', pk=article.pk)
    else:
        form = CommentForm()

    return render(request, 'articles/article_detail.html', {
        'article': article,
        'comments': comments,
        'form': form,
        'categories': CATEGORIES,
    })

# 🖼 Upload AI Image
@login_required
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        title = request.POST.get('title', 'Untitled AI Image')
        prompt = request.POST.get('description', '')

        if image_file:
            AIImage.objects.create(
                user=request.user,
                title=title,
                prompt_used=prompt,
                image=image_file,
            )
            return JsonResponse({
                'status': 'success',
                'message': '✅ AI image uploaded successfully.',
                'redirect_url': '/ai-images/'
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'No image selected!'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

# 🎞 Upload AI Video
@login_required
def upload_video(request):
    if request.method == 'POST':
        title = request.POST.get('title', 'Untitled AI Video')
        description = request.POST.get('description', '')
        video_file = request.FILES.get('video')

        if not video_file:
            return JsonResponse({'status': 'error', 'message': '⚠️ Please upload a video.'}, status=400)

        try:
            video = AIVideo.objects.create(
                user=request.user,
                title=title,
                prompt_used=description,
                video=video_file
            )
            return JsonResponse({
                'status': 'success',
                'message': '✅ Video uploaded successfully.',
                'video_id': video.id
            }, status=200)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f"⚠️ Error: {str(e)}"}, status=500)

# 🖼 AI Image Gallery
def ai_image_gallery(request):
    ai_images = AIImage.objects.select_related('user').order_by('-generated_at')
    paginator = Paginator(ai_images, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'articles/ai_image_gallery.html', {
        'page_obj': page_obj,
        'images': page_obj.object_list,
        'categories': CATEGORIES,
    })

# 🎞 AI Video Gallery
def ai_video_gallery(request):
    ai_videos = AIVideo.objects.select_related('user').order_by('-generated_at')
    return render(request, 'articles/ai_video_gallery.html', {
        'videos': ai_videos,
        'categories': CATEGORIES,
    })

# 📝 Edit Article
@login_required
def edit_article(request, pk):
    article = get_object_or_404(Article, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Article updated successfully.')
            return redirect('article_detail', pk=article.pk)
    else:
        form = ArticleForm(instance=article)

    return render(request, 'articles/edit_article.html', {
        'form': form,
        'article': article,
        'categories': CATEGORIES,
    })

# ❌ Delete Article
@login_required
def delete_article(request, pk):
    article = get_object_or_404(Article, pk=pk, user=request.user)
    if request.method == 'POST':
        article.delete()
        messages.success(request, '🗑️ Article deleted successfully.')
        return redirect('article_list')

    return render(request, 'articles/delete_article.html', {'article': article})

def search_results(request):
    query = request.GET.get('q', '')

    articles = Article.objects.filter(
        Q(title__icontains=query) |
        Q(summary__icontains=query) |
        Q(body__icontains=query)
    )

    ai_images = AIImage.objects.filter(
        Q(title__icontains=query) |
        Q(prompt_used__icontains=query)
    )

    ai_videos = AIVideo.objects.filter(
        Q(title__icontains=query) |
        Q(prompt_used__icontains=query)
    )

    return render(request, 'articles/search_results.html', {
        'query': query,
        'articles': articles,
        'images': ai_images,
        'videos': ai_videos,
    })

def ai_image_detail(request, pk):
    image = get_object_or_404(AIImage, pk=pk)
    # Make sure to query the comments
    comments = ImageComment.objects.filter(image=image).order_by('-created_at')

    return render(request, 'articles/ai_image_detail.html', {
        'image': image,
        'comments': comments,  # Pass comments to the template
        'categories': CATEGORIES,
    })

def ai_video_detail(request, pk):
    video = get_object_or_404(AIVideo, pk=pk)
    comments = video.comments.all()  # Get all comments
    return render(request, 'articles/ai_video_detail.html', {
        'video': video,
        'comments': comments,
        'categories': CATEGORIES
    })

@login_required
def delete_ai_image(request, pk):
    image = get_object_or_404(AIImage, pk=pk)
    if image.user == request.user:
        image.delete()
        messages.success(request, '✅ Your image has been deleted.')
    else:
        messages.error(request, '⚠️ You are not authorized to delete this image.')
    return redirect('ai_image_gallery')

@login_required
def delete_ai_video(request, pk):
    video = get_object_or_404(AIVideo, pk=pk)
    if video.user == request.user:
        video.delete()
        messages.success(request, '✅ Your video has been deleted.')
    else:
        messages.error(request, '⚠️ You are not authorized to delete this video.')
    return redirect('ai_video_gallery')

@login_required
def add_image_comment(request, pk):
    image = get_object_or_404(AIImage, pk=pk)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            ImageComment.objects.create(
                image=image,
                user=request.user,
                content=content
            )
            messages.success(request, "Your comment has been added!")
    return redirect('ai_image_detail', pk=image.pk)

def ai_image_detail(request, pk):
    image = get_object_or_404(AIImage, pk=pk)
    comments = image.comments.all()  # Get all comments
    return render(request, 'articles/ai_image_detail.html', {
        'image': image,
        'comments': comments,
        'categories': CATEGORIES
    })

@login_required
def add_video_comment(request, pk):
    video = get_object_or_404(AIVideo, pk=pk)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            VideoComment.objects.create(
                video=video,
                user=request.user,
                content=content
            )
            messages.success(request, "Your comment has been added!")
    return redirect('ai_video_detail', pk=video.pk)

@login_required
def approve_article(request, pk):
    # Only staff can approve articles
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to approve articles.")
        return redirect('article_list')

    article = get_object_or_404(Article, pk=pk)
    article.moderation_status = 'approved'
    article.save()

    messages.success(request, f"Article '{article.title}' has been approved.")
    return redirect('article_detail', pk=pk)

@login_required
def reject_article(request, pk):
    # Only staff can reject articles
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to reject articles.")
        return redirect('article_list')

    article = get_object_or_404(Article, pk=pk)
    article.moderation_status = 'rejected'
    article.save()

    messages.success(request, f"Article '{article.title}' has been rejected.")
    return redirect('article_detail', pk=pk)

