from openai import OpenAI
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from .models import Article, Comment
from .forms import ArticleForm, CommentForm

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Define categories globally
CATEGORIES = dict(Article.CATEGORY_CHOICES)  # Ensuring consistent format

### 🚀 AI-Powered Article Generation ###
def generate_article(title, summary, category):
    prompt = f"Write a news article titled '{title}' in the {category} category."
    if summary:
        prompt += f" Here's a brief summary: {summary}"

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return "Error: AI failed to generate content. Please try again."

### 🌍 PUBLIC: Homepage - List All Articles ###
def article_list(request):
    category = request.GET.get('category', 'All')  # Default to 'All' if no category is selected

    if category == 'All':
        # Show all articles when "All Articles" is selected
        articles = Article.objects.order_by('-created_at')
    elif category == "General":
        # Show only "General" category articles
        articles = Article.objects.filter(category="General").order_by('-created_at')
    else:
        # Show articles of the selected category
        articles = Article.objects.filter(category=category).order_by('-created_at')

    return render(request, 'articles/article_list.html', {
        'articles': articles,
        'categories': CATEGORIES,  # Pass the consistent categories here
        'selected_category': category,  # Pass selected category for active state in navigation
    })

### 🔎 View Single Article ###
def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
    comments = article.comments.all()  # Get all comments related to this article

    # Add categories to be passed to the template
    categories = CATEGORIES  # Make sure categories are passed to the template

    if request.method == 'POST' and request.user.is_authenticated:
        form = CommentForm(request.POST)
        if form.is_valid():
            # Save the comment with the associated article and user
            comment = form.save(commit=False)
            comment.article = article  # Associate the comment with the current article
            comment.user = request.user  # Associate the comment with the current user
            comment.save()  # Save the comment to the database
            messages.success(request, "Your comment has been added!")
            return redirect('article_detail', pk=article.pk)  # Redirect to the article detail page
    else:
        form = CommentForm()

    return render(request, 'articles/article_detail.html', {
        'article': article,
        'comments': comments,
        'form': form,  # Pass the form to the template for comment submission
        'categories': categories,  # Pass categories to the template
    })

### 🔐 Sign-Up View ###``
def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('article_list')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def new_article(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)

        # Extract the form data first
        title = request.POST.get('title', '')
        summary = request.POST.get('summary', '')
        category = request.POST.get('category', 'General')

        # Generate AI content before form validation
        article_text = generate_article(title, summary, category)

        if not article_text or article_text.startswith("Error"):
            messages.error(request, "⚠️ OpenAI failed to generate an article. Please try again.")
            return redirect('new_article')

        # Create modified POST data with the generated body
        post_with_body = request.POST.copy()
        post_with_body['body'] = article_text

        # Re-initialize the form with the updated POST data
        form = ArticleForm(post_with_body, request.FILES)

        if form.is_valid():
            # Save the article
            article = form.save(commit=False)
            article.user = request.user
            article.save()

            messages.success(request, '✅ Article generated successfully.')
            return redirect('article_list')

        # Print form errors if validation fails
        print("❌ Form is invalid.")
        print(form.errors)
        messages.error(request, "⚠️ Form validation failed. Please check your input.")

    else:
        form = ArticleForm()

    return render(request, 'articles/new_article.html', {'form': form, 'categories': CATEGORIES})

### 📝 Edit Existing Article ###
@login_required
def edit_article(request, pk):
    article = get_object_or_404(Article, pk=pk, user=request.user)

    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)  # ✅ Include request.FILES
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Article updated successfully.')
            return redirect('article_detail', pk=article.pk)
    else:
        form = ArticleForm(instance=article)

    return render(request, 'articles/edit_article.html', {
        'form': form,
        'article': article,
        'categories': CATEGORIES,  # Pass consistent categories here
    })

### 🗑 Delete Article ###
@login_required
def delete_article(request, pk):
    article = get_object_or_404(Article, pk=pk, user=request.user)
    if request.method == 'POST':
        article.delete()
        messages.success(request, '🗑️ Article deleted successfully.')
        return redirect('article_list')

    return render(request, 'articles/delete_article.html', {'article': article})
