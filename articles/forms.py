from django import forms
from .models import Article, Comment, AIImage, AIVideo
import os
import logging
from django.db import models

logger = logging.getLogger(__name__)

class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=forms.HiddenInput(), required=False)
    image = forms.ImageField(required=False)  # Use forms.ImageField instead of models.ImageField
    video = forms.FileField(required=False)  # ✅ Add video field to support AIVideo uploads

    class Meta:
        model = Article
        fields = ['title', 'summary', 'category', 'image', 'body']  # `video` is handled manually in views

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            if self.instance and self.instance.image:
                return self.instance.image
            return None

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
        fields = ['content']

class AIImageForm(forms.ModelForm):
    class Meta:
        model = AIImage
        fields = ['image', 'prompt_used']

class AIVideoForm(forms.ModelForm):
    class Meta:
        model = AIVideo
        fields = ['video', 'prompt_used']

