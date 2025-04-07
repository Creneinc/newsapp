from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Article, Comment, AIImage, AIVideo
from .forms import ArticleForm, CommentForm
import requests
import json


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
        form = ArticleForm(post_data, request.FILES)

        if form.is_valid():
            article = form.save(commit=False)
            article.user = request.user
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
                "stream": False
            })
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print(f"Ollama Error: {e}")
        return "Error: AI failed to generate content. Please try again."


# 🖼 Upload AI Image
@login_required
def upload_image(request):
    if request.method == 'POST':
        title = request.POST.get('title', 'Untitled AI Image')
        prompt = request.POST.get('description', '')  # ✅ updated to match form
        image_file = request.FILES.get('image')

        if not image_file:
            messages.error(request, "⚠️ Please upload an image.")
            return redirect('ai_image_gallery')

        AIImage.objects.create(
            user=request.user,
            title=title,
            prompt_used=prompt,  # ✅ this will now have content
            image=image_file,
        )

        messages.success(request, "✅ AI image uploaded successfully.")
        return redirect('ai_image_gallery')

# 🎞 Upload AI Video
@login_required
def upload_video(request):
    if request.method == 'POST':
        title = request.POST.get('title', 'Untitled AI Video')
        description = request.POST.get('description', '')  # ✅ updated here
        video_file = request.FILES.get('video')

        if not video_file:
            messages.error(request, "⚠️ Please upload a video.")
            return redirect('ai_video_gallery')

        AIVideo.objects.create(
            user=request.user,
            title=title,
            prompt_used=description,  # ✅ save to correct field
            video=video_file,
        )

        messages.success(request, "✅ AI video uploaded successfully.")
        return redirect('ai_video_gallery')


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
