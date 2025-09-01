from django.contrib import admin
from .models import LearningHistory, UserProfile, LearningStatistics, Vocabulary

@admin.register(LearningHistory)
class LearningHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'session_id_short',
        'user',
        'learning_type',
        'created_at',
        'image_filename',
        'ocr_status',
        'tts_status',
        'processing_time_ocr',
        'processing_time_tts'
    ]
    list_filter = [
        'learning_type',
        'ocr_status',
        'tts_status',
        'created_at',
        'user'
    ]
    search_fields = [
        'session_id',
        'extracted_text',
        'image_filename',
        'user__username',
        'user__email'
    ]
    readonly_fields = [
        'session_id',
        'created_at',
        'updated_at',
        'processing_time_ocr',
        'processing_time_tts'
    ]
    fieldsets = [
        ('Session Information', {
            'fields': [
                'session_id',
                'user',
                'learning_type',
                'created_at',
                'updated_at'
            ]
        }),
        ('Image Upload', {
            'fields': [
                'uploaded_image',
                'image_filename'
            ]
        }),
        ('OCR Results', {
            'fields': [
                'ocr_status',
                'extracted_text',
                'ocr_error',
                'processing_time_ocr'
            ]
        }),
        ('TTS Results', {
            'fields': [
                'tts_status',
                'audio_file',
                'audio_file_path',
                'audio_filename',
                'tts_error',
                'processing_time_tts'
            ]
        }),
        ('Language Learning', {
            'fields': [
                'target_language',
                'difficulty_level',
                'word_count',
                'is_favorited',
                'user_rating',
                'times_played',
                'last_played_at'
            ]
        })
    ]
    
    def session_id_short(self, obj):
        return str(obj.session_id)[:8] + "..."
    session_id_short.short_description = "Session ID"
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')
    
    def has_add_permission(self, request):
        # Prevent manual creation of sessions through admin
        return False

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'target_language',
        'voice_preference',
        'total_sessions',
        'total_words_learned',
        'learning_streak',
        'created_at'
    ]
    list_filter = [
        'target_language',
        'voice_preference',
        'created_at'
    ]
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('User Information', {
            'fields': ['user']
        }),
        ('Learning Preferences', {
            'fields': [
                'target_language',
                'voice_preference'
            ]
        }),
        ('Statistics', {
            'fields': [
                'learning_streak',
                'total_sessions',
                'total_words_learned'
            ]
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at']
        })
    ]

@admin.register(LearningStatistics)
class LearningStatisticsAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'date',
        'sessions_completed',
        'words_learned',
        'time_spent_minutes'
    ]
    list_filter = [
        'date',
        'user'
    ]
    search_fields = [
        'user__username',
        'user__email'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'date'

@admin.register(Vocabulary)
class VocabularyAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'word',
        'language',
        'mastery_level',
        'times_reviewed',
        'last_reviewed',
        'created_at'
    ]
    list_filter = [
        'language',
        'mastery_level',
        'created_at',
        'user'
    ]
    search_fields = [
        'word',
        'definition',
        'user__username'
    ]
    readonly_fields = ['created_at']
    
    fieldsets = [
        ('Word Information', {
            'fields': [
                'user',
                'word',
                'definition',
                'language'
            ]
        }),
        ('Learning Progress', {
            'fields': [
                'mastery_level',
                'times_reviewed',
                'last_reviewed',
                'learning_session'
            ]
        }),
        ('Timestamps', {
            'fields': ['created_at']
        })
    ]