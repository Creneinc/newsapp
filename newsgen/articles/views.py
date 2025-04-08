from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from .models import Article, Comment, AIImage, AIVideo
from .forms import ArticleForm, CommentForm
import requests
import json
import logging

logger = logging.getLogger(__name__)

CATEGORIES = dict(Article.CATEGORY_CHOICES)

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
        'categories': CATEGORIES  # This should already exist at the top
    })

# 🌍 Homepage: Article List with Optional Category Filter
def article_list(request):
    category = request.GET.get('category', 'All')
    search_query = request.GET.get('search', '')

    articles = Article.objects.all()

    if category and category != 'All':
        articles = articles.filter(category=category)

    if search_query:
        articles = articles.filter(title__icontains=search_query)

    articles = articles.order_by('-created_at')

    return render(request, 'articles/article_list.html', {
        'articles': articles,
        'categories': CATEGORIES,
        'selected_category': category,
    })


# 🔎 Article Detail + Comments
def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
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


# 🆕 Generate News Article
@login_required
def new_article(request):
    if request.method == 'POST':
        title = request.POST.get('title', '')
        summary = request.POST.get('summary', '')
        category = request.POST.get('category', 'General')

        article_text = generate_article(title, summary, category)
        if not article_text or article_text.startswith("Error"):
            messages.error(request, "⚠️ Failed to generate article. Please try again.")
            return redirect('new_article')

        post_data = request.POST.copy()
        post_data['body'] = article_text
        form = ArticleForm(post_data, request.FILES)  # Make sure to pass request.FILES

        if form.is_valid():
            article = form.save(commit=False)
            article.user = request.user  # Ensure the logged-in user is assigned to the article
            article.save()
            messages.success(request, '✅ Article generated successfully.')
            return redirect('article_detail', pk=article.pk)
        else:
            messages.error(request, "⚠️ Form validation failed.")
    else:
        form = ArticleForm()

    return render(request, 'articles/new_article.html', {
        'form': form,
        'categories': CATEGORIES,
    })

# 🆕 Generate Article View (AJAX)
def create_article(request):
    if request.method == 'POST':
        try:
            # Access form data and files directly from the request
            title = request.POST.get('title', '')
            summary = request.POST.get('summary', '')
            category = request.POST.get('category', 'General')

            # Validate the data
            if not title or not summary or not category:
                return JsonResponse({'status': 'error', 'message': 'All fields are required!'}, status=400)

            # Generate the article content
            article_content = generate_article(title, summary, category)

            if article_content.startswith("Error"):
                return JsonResponse({'status': 'error', 'message': article_content}, status=400)

            # Save the article using the ArticleForm
            form = ArticleForm({
                'title': title,
                'summary': summary,
                'category': category,
                'body': article_content
            }, request.FILES)  # Ensure to pass request.FILES for file handling

            if form.is_valid():
                article = form.save(commit=False)
                article.user = request.user
                article.save()

                return JsonResponse({'status': 'success', 'message': 'Article created successfully', 'article_id': article.id})
            else:
                return JsonResponse({'status': 'error', 'message': 'Form validation failed'}, status=400)

        except Exception as e:
            # Log the exception for debugging
            logger.error(f"Error in create_article: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred while processing the request.'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


# 🚀 Mistral AI Article Generator
def generate_article(title, summary, category):
    prompt = f"Write a full news article in the '{category}' category based on the following details.\n\nTitle: {title}\n"
    if summary:
        prompt += f"Summary: {summary}\n"
    prompt += "\nOnly write the body of the article. Do not include the title."

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "model": "mistral",
                "prompt": prompt,
                "stream": False  # Set to False to get the full response immediately
            })
        )
        response.raise_for_status()
        # Ensure a proper response is received and return it
        response_json = response.json()
        if "response" in response_json:
            return response_json["response"]
        else:
            return "Error: AI returned no content. Please try again."
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return "Error: Unable to reach the AI service. Please try again later."
    except Exception as e:
        print(f"General Error: {e}")
        return "Error: AI failed to generate content. Please try again."



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
            response_data = {
                'status': 'success',
                'message': '✅ AI image uploaded successfully.',
                'redirect_url': '/ai-images/'  # Change this URL as per your use case
            }
            return JsonResponse(response_data)
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

        # Create the video object
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
    return render(request, 'articles/ai_image_detail.html', {
        'image': image,
        'categories': CATEGORIES  # ✅ added this line
    })

def ai_video_detail(request, pk):
    video = get_object_or_404(AIVideo, pk=pk)
    return render(request, 'articles/ai_video_detail.html', {
        'video': video,
        'categories': CATEGORIES  # ✅ include it here too
    })

@login_required
def delete_ai_image(request, pk):
    # Get the AI image
    image = get_object_or_404(AIImage, pk=pk)

    # Check if the current user is the creator
    if image.user == request.user:
        image.delete()
        messages.success(request, '✅ Your image has been deleted.')
    else:
        messages.error(request, '⚠️ You are not authorized to delete this image.')

    return redirect('ai_image_gallery')  # Redirect back to the gallery

@login_required
def delete_ai_video(request, pk):
    # Get the AI video
    video = get_object_or_404(AIVideo, pk=pk)

    # Check if the current user is the creator
    if video.user == request.user:
        video.delete()
        messages.success(request, '✅ Your video has been deleted.')
    else:
        messages.error(request, '⚠️ You are not authorized to delete this video.')

    return redirect('ai_video_gallery')  # Redirect back to the video gallery
