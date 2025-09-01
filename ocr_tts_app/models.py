from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
import uuid
import os

def upload_to_images(instance, filename):
    """Generate upload path for images"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    user_folder = f"user_{instance.user.id}" if hasattr(instance, 'user') and instance.user else "anonymous"
    return os.path.join('images', user_folder, filename)

def upload_to_audio(instance, filename):
    """Generate upload path for audio files"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    user_folder = f"user_{instance.user.id}" if hasattr(instance, 'user') and instance.user else "anonymous"
    return os.path.join('audio', user_folder, filename)

class UserProfile(models.Model):
    """Extended user profile for language learning platform"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    target_language = models.CharField(
        max_length=10, 
        choices=settings.SUPPORTED_LANGUAGES,
        default=settings.DEFAULT_TARGET_LANGUAGE
    )
    voice_preference = models.CharField(
        max_length=50,
        choices=[
            ('male', 'Male Voice'),
            ('female', 'Female Voice'),
            ('neutral', 'Neutral Voice'),
        ],
        default='female'
    )
    learning_streak = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    total_words_learned = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

class LearningHistory(models.Model):
    """Model to store user's learning history and OCR/TTS results"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    LEARNING_TYPE_CHOICES = [
        ('image_ocr', 'Image OCR'),
        ('text_input', 'Direct Text Input'),
        ('practice', 'Practice Session'),
    ]
    
    # Core identification
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_sessions')
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    learning_type = models.CharField(max_length=20, choices=LEARNING_TYPE_CHOICES, default='image_ocr')
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Image upload
    uploaded_image = models.ImageField(upload_to=upload_to_images, null=True, blank=True)
    image_filename = models.CharField(max_length=255, blank=True)
    
    # OCR results
    ocr_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    extracted_text = models.TextField(blank=True)
    ocr_error = models.TextField(blank=True)
    
    # TTS results
    tts_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    audio_file = models.FileField(upload_to=upload_to_audio, null=True, blank=True)
    audio_file_path = models.CharField(max_length=500, blank=True)  # Backward compatibility
    audio_filename = models.CharField(max_length=255, blank=True)
    tts_error = models.TextField(blank=True)
    
    # Language learning specific fields
    target_language = models.CharField(max_length=10, default='en')
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ],
        default='beginner'
    )
    word_count = models.PositiveIntegerField(default=0)
    
    # Processing metadata
    processing_time_ocr = models.FloatField(null=True, blank=True)  # in seconds
    processing_time_tts = models.FloatField(null=True, blank=True)  # in seconds
    
    # Dictionary lookup results (for single words)
    is_single_word = models.BooleanField(default=False)
    word_definitions = models.JSONField(null=True, blank=True)  # Store dictionary definitions
    dictionary_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # User interaction tracking
    times_played = models.PositiveIntegerField(default=0)
    last_played_at = models.DateTimeField(null=True, blank=True)
    is_favorited = models.BooleanField(default=False)
    user_rating = models.PositiveSmallIntegerField(
        null=True, 
        blank=True,
        choices=[(i, f"{i} Star{'s' if i != 1 else ''}") for i in range(1, 6)]
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Learning Session"
        verbose_name_plural = "Learning Sessions"
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'learning_type']),
            models.Index(fields=['user', 'is_favorited']),
        ]
    
    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"{username} - Session {str(self.session_id)[:8]} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def is_completed(self):
        """Check if both OCR and TTS are completed"""
        return self.ocr_status == 'completed' and self.tts_status == 'completed'
    
    @property
    def has_errors(self):
        """Check if there are any errors"""
        return self.ocr_status == 'failed' or self.tts_status == 'failed'
    
    @property
    def audio_url(self):
        """Get the URL for the audio file"""
        if self.audio_file:
            return self.audio_file.url
        elif self.audio_file_path:
            # Backward compatibility
            audio_path = self.audio_file_path
            if audio_path.startswith('media/'):
                audio_path = audio_path[6:]  # Remove 'media/' prefix
            return f"/media/{audio_path}"
        return None
    
    def increment_play_count(self):
        """Increment the play count and update last played time"""
        self.times_played += 1
        self.last_played_at = timezone.now()
        self.save(update_fields=['times_played', 'last_played_at'])
    
    def get_difficulty_display_color(self):
        """Get Bootstrap color class for difficulty level"""
        colors = {
            'beginner': 'success',
            'intermediate': 'warning',
            'advanced': 'danger'
        }
        return colors.get(self.difficulty_level, 'secondary')

# Compatibility alias for existing code
OCRTTSSession = LearningHistory

class LearningStatistics(models.Model):
    """Model to track daily learning statistics"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_stats')
    date = models.DateField()
    sessions_completed = models.PositiveIntegerField(default=0)
    words_learned = models.PositiveIntegerField(default=0)
    time_spent_minutes = models.PositiveIntegerField(default=0)  # in minutes
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']
        verbose_name = "Learning Statistics"
        verbose_name_plural = "Learning Statistics"
    
    def __str__(self):
        return f"{self.user.username} - {self.date}"

class Vocabulary(models.Model):
    """Model to store vocabulary words learned by users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vocabulary')
    word = models.CharField(max_length=100)
    definition = models.TextField()
    language = models.CharField(max_length=10, choices=settings.SUPPORTED_LANGUAGES)
    learning_session = models.ForeignKey(LearningHistory, on_delete=models.SET_NULL, null=True, blank=True)
    mastery_level = models.CharField(
        max_length=20,
        choices=[
            ('learning', 'Learning'),
            ('practicing', 'Practicing'),
            ('mastered', 'Mastered'),
        ],
        default='learning'
    )
    times_reviewed = models.PositiveIntegerField(default=0)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'word', 'language']
        ordering = ['-created_at']
        verbose_name = "Vocabulary Word"
        verbose_name_plural = "Vocabulary Words"
    
    def __str__(self):
        return f"{self.user.username} - {self.word} ({self.language})"
