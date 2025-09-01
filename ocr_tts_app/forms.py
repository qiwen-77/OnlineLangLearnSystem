from django import forms
from .models import LearningHistory

class ImageUploadForm(forms.ModelForm):
    """Form for uploading images"""
    
    class Meta:
        model = LearningHistory
        fields = ['uploaded_image']
        widgets = {
            'uploaded_image': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': 'image/*',
                'required': True
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['uploaded_image'].label = 'Upload Image'
        self.fields['uploaded_image'].help_text = 'Select an image file containing text to extract'

class TextProcessingForm(forms.Form):
    """Form for manual text input (for testing TTS without OCR)"""
    text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter text to convert to speech...'
        }),
        max_length=1000,
        help_text='Enter up to 1000 characters'
    )
