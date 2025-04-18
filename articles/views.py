from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from articles.models import get_category_dict
from .models import Article, Comment, AIImage, AIVideo, ImageComment, VideoComment, get_category_dict, SiteSettings
from .forms import ArticleForm, CommentForm
from articles.tasks import generate_article_task
from django.template.loader import render_to_string
from celery.result import AsyncResult
from uuid import uuid4
from django.utils.timezone import now
from datetime import timedelta
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

def generate_article_with_ollama(title, summary, category):
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


def generate_article_with_groq(title, summary, category):
    prompt = f"Write a full news article in the '{category}' category based on the following details.\n\nTitle: {title}\n"
    if summary:
        prompt += f"Summary: {summary}\n"
    prompt += "\nOnly write the body of the article. Do not include the title."

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": "You are a helpful journalist AI."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "stream": False
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            logger.warning(f"Groq failed: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Groq error: {str(e)}")

    return None

# 📜 AJAX Article Creation
@login_required
def create_article(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

    try:
        title = request.POST.get('title', '').strip()
        summary = request.POST.get('summary', '').strip()
        category = request.POST.get('category', 'General').strip()

        if not title:
            return JsonResponse({'status': 'error', 'message': 'Title is required!'}, status=400)

        image = request.FILES.get('image')

        # ✅ Fetch site-wide setting
        site_settings = SiteSettings.objects.first()
        auto_approve = site_settings.auto_approve_articles if site_settings else False

        article = Article.objects.create(
            user=request.user,
            title=title,
            summary=summary,
            category=category,
            image=image,
            body="⏳ Generating article...",
            moderation_status='approved' if auto_approve else 'pending',
        )

        content = generate_article_with_groq(title, summary, category)
        if not content:
            logger.info("Fallback to local Mistral (Ollama)...")
            content = generate_article_with_ollama(title, summary, category)

        article.body = content if content else f"⚠️ Generation failed. Here’s your summary:\n\n{summary}"
        article.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Article created!',
            'article_id': article.id,
            'slug': slugify(title)
        })

    except Exception as e:
        logger.error(f"Unexpected error in create_article: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred. Please try again.'}, status=500)

@csrf_exempt
def stream_article_generation(request):
    if request.method != 'POST' or not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized or invalid request'}, status=403)

    data = json.loads(request.body)
    title = data.get('title', '').strip()
    summary = data.get('summary', '').strip()
    category = data.get('category', 'General').strip()
    article_id = data.get('article_id')

    if not title or not article_id:
        return JsonResponse({'error': 'Missing data'}, status=400)

    prompt = f"Write a full news article in the '{category}' category based on the following details.\n\nTitle: {title}\n"
    if summary:
        prompt += f"Summary: {summary}\n"
    prompt += "\nOnly write the body of the article. Do not include the title."

    def event_stream():
        yield "data: ⏳ Generating article...\n\n"
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "mixtral-8x7b-32768",
                    "messages": [
                        {"role": "system", "content": "You are a helpful journalist AI."},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": True
                },
                stream=True,
                timeout=60
            )

            article = Article.objects.get(pk=article_id)
            full_content = ""

            for line in response.iter_lines():
                if line and line.startswith(b"data: "):
                    chunk = json.loads(line[6:])
                    content = chunk["choices"][0]["delta"].get("content")
                    if content:
                        full_content += content
                        yield f"data: {content}\n\n"

            if full_content:
                article.body = full_content.strip()
                article.slug = slugify(title)
                article.save()

        except Exception as e:
            yield f"data: ⚠️ Error occurred: {str(e)}\n\n"

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')


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

def home_view(request):
    # Mark as main page
    is_main_page = True

    # Fetch homepage content
    categories = get_category_dict()
    articles = Article.objects.filter(moderation_status='approved').order_by('-created_at')

    trending_manual = list(Article.objects.filter(moderation_status='approved', is_trending=True).order_by('-created_at')[:8])

    if len(trending_manual) < 8:
        fill_count = 8 - len(trending_manual)
        additional = Article.objects.filter(moderation_status='approved')\
            .exclude(id__in=[a.id for a in trending_manual])\
            .order_by('-view_count')[:fill_count]
        popular_articles = trending_manual + list(additional)
    else:
        popular_articles = trending_manual

    # Recommendation logic (excluding already shown articles)
    recommended_articles = []
    if request.user.is_authenticated:
        exclude_ids = [a.id for a in popular_articles]
        recommended_articles = Article.objects.filter(moderation_status='approved')\
            .exclude(id__in=exclude_ids)\
            .order_by('-created_at')[:4]

    recommended_articles = []
    if request.user.is_authenticated:
        recommended_articles = Article.objects.filter(
            moderation_status='approved'
        ).exclude(id__in=[a.id for a in popular_articles]).order_by('-created_at')[:4]

    ai_images = AIImage.objects.all().order_by('-generated_at')[:1]
    ai_videos = AIVideo.objects.all().order_by('-generated_at')[:1]

    context = {
        'articles': articles,
        'popular_articles': popular_articles,
        'recommended_articles': recommended_articles,
        'ai_images': ai_images,
        'ai_videos': ai_videos,
        'categories': categories,
        'is_main_page': is_main_page,
    }

    return render(request, 'articles/article_list.html', context)

def article_list(request):
    # Get query parameters
    category = request.GET.get('category')
    show_all = request.GET.get('show_all')

    # Special case for "category=All" - treat as show_all
    if category == 'All':
        category = None
        show_all = 'true'

    # Determine if this is the main page (should show trending and AI showcase)
    is_main_page = request.path == '/'

    # Get articles
    articles = Article.objects.filter(moderation_status='approved').order_by('-created_at')

    # Apply category filter only if needed
    if category and category != 'All':
        articles = articles.filter(category=category)

    # Main page sections (Trending + AI Showcase)
    popular_articles = []
    recommended_articles = []
    ai_images = []
    ai_videos = []

    # Get these for main page only
    if is_main_page:
        popular_articles = Article.objects.filter(
            moderation_status='approved'
        ).order_by('-view_count', '-created_at')[:4]

        if request.user.is_authenticated:
            recommended_articles = Article.objects.filter(
                moderation_status='approved'
            ).exclude(id__in=[a.id for a in popular_articles]).order_by('-created_at')[:4]

        ai_images = AIImage.objects.all().order_by('-generated_at')[:1]
        ai_videos = AIVideo.objects.all().order_by('-generated_at')[:1]

    # Get categories for all pages
    categories = get_category_dict()

    # Define context outside the if condition so it's always available
    context = {
        'articles': articles,
        'popular_articles': popular_articles,
        'recommended_articles': recommended_articles,
        'ai_images': ai_images,
        'ai_videos': ai_videos,
        'categories': categories,
        'is_main_page': is_main_page,
    }

    return render(request, 'articles/article_list.html', context)

# 🔎 Article Detail + Comments
def article_detail(request, pk, slug):
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
            return redirect('article_detail', pk=article.pk, slug=slugify(article.title))
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
def edit_article(request, pk, slug):
    article = get_object_or_404(Article, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Article updated successfully.')
            return redirect('article_detail', pk=article.pk, slug=slugify(article.title))
    else:
        form = ArticleForm(instance=article)

    return render(request, 'articles/edit_article.html', {
        'form': form,
        'article': article,
        'categories': CATEGORIES,
    })

# ❌ Delete Article
@login_required
def delete_article(request, pk, slug):
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

def ai_image_detail(request, pk, slug=None):
    image = get_object_or_404(AIImage, pk=pk)
    # Make sure to query the comments
    comments = ImageComment.objects.filter(image=image).order_by('-created_at')

    return render(request, 'articles/ai_image_detail.html', {
        'image': image,
        'comments': comments,  # Pass comments to the template
        'categories': CATEGORIES,
    })

def ai_video_detail(request, pk, slug=None):
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

@require_POST
@csrf_exempt
def like_article(request, pk):
    try:
        article = Article.objects.get(pk=pk)
        article.likes += 1
        article.save()
        return JsonResponse({'status': 'success', 'likes': article.likes})
    except Article.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Article not found'}, status=404)

@login_required
def like_ai_image(request, pk):
    image_key = f"liked_image_{pk}"
    last_like_key = f"last_like_time_{pk}"

    last_like = request.session.get(last_like_key)
    if last_like:
        last_time = now() - timedelta(seconds=10)
        if last_like > str(last_time):
            return JsonResponse({'status': 'error', 'message': 'Please wait before liking again.'}, status=429)

    if request.session.get(image_key):
        return JsonResponse({'status': 'error', 'message': 'Already liked.'}, status=403)

    try:
        image = AIImage.objects.get(pk=pk)
        image.likes += 1
        image.save()

        request.session[image_key] = True
        request.session[last_like_key] = str(now())

        return JsonResponse({'status': 'success', 'likes': image.likes})
    except AIImage.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Image not found'}, status=404)

@login_required
def like_ai_video(request, pk):
    video_key = f"liked_video_{pk}"
    last_like_key = f"last_like_time_video_{pk}"

    last_like = request.session.get(last_like_key)
    if last_like:
        last_time = now() - timedelta(seconds=10)
        if last_like > str(last_time):
            return JsonResponse({'status': 'error', 'message': 'Please wait before liking again.'}, status=429)

    if request.session.get(video_key):
        return JsonResponse({'status': 'error', 'message': 'Already liked.'}, status=403)

    try:
        video = AIVideo.objects.get(pk=pk)
        video.likes += 1
        video.save()

        request.session[video_key] = True
        request.session[last_like_key] = str(now())

        return JsonResponse({'status': 'success', 'likes': video.likes})
    except AIVideo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Video not found'}, status=404)
