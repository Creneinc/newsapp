from django import forms
from .models import Article, Comment
import os
import logging

# Set up logging
logger = logging.getLogger(__name__)

class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Article
        fields = ['title', 'summary', 'category', 'image', 'body']

    def clean_image(self):
        image = self.cleaned_data.get("image")

        if not image:
            if self.instance and self.instance.image:
                return self.instance.image
            return None

        # Log image details for debugging (for uploaded file)
        logger.info(f"Image upload details: name={image.name}, size={image.size}")

        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        ext = os.path.splitext(image.name)[1].lower()

        if ext not in valid_extensions:
            logger.warning(f"Rejected file with extension: {ext}")
            raise forms.ValidationError(f"Unsupported file extension. Supported formats: {', '.join(valid_extensions)}")

        return image

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']  # Only the content field from the Comment model
