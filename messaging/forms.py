from django import forms
from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Type your message...',
                'maxlength': '2000',
                'autofocus': True,
            }),
        }
        labels = {
            'body': '',
        }

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('Write a message before sending.')
        if len(body) > 2000:
            raise forms.ValidationError('Messages are limited to 2000 characters.')
        return body
