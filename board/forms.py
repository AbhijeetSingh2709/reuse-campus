from django import forms
from .models import BoardRequest


class BoardRequestForm(forms.ModelForm):
    class Meta:
        model = BoardRequest
        fields = ['title', 'description', 'category']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Add more details about what you need...'
            }),
        }
