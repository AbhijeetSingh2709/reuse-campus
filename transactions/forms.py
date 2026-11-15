from django import forms
from .models import BuyRequest, RentRequest
import datetime


class BuyRequestForm(forms.ModelForm):
    class Meta:
        model = BuyRequest
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional message to the seller...'
            }),
        }


class RentRequestForm(forms.ModelForm):
    class Meta:
        model = RentRequest
        fields = ['start_date', 'end_date', 'message']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional message to the owner...'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end:
            if start < datetime.date.today():
                self.add_error('start_date', 'Start date cannot be in the past.')
            if end <= start:
                self.add_error('end_date', 'End date must be after start date.')
        return cleaned_data
