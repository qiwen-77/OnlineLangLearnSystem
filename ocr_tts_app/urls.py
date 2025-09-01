from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Learning features (require authentication)
    path('upload/', views.UploadView.as_view(), name='upload_form'),
    path('upload/process/', views.UploadImageView.as_view(), name='upload'),
    path('text-to-speech/', views.TextToSpeechView.as_view(), name='text_to_speech'),
    path('translate/', views.TranslationView.as_view(), name='translation'),
    path('result/<uuid:session_id>/', views.ResultView.as_view(), name='result'),
    path('export/<uuid:session_id>/', views.ExportLearningNoteView.as_view(), name='export_learning_note'),
    path('sessions/', views.SessionListView.as_view(), name='session_list'),
    path('sessions/delete/<uuid:session_id>/', views.DeleteSessionView.as_view(), name='delete_session'),
    path('sessions/delete_all/', views.DeleteAllSessionsView.as_view(), name='delete_all_sessions'),
    
    # API endpoints
    path('api/status/<uuid:session_id>/', views.ProcessingStatusView.as_view(), name='processing_status'),
    path('api/tts/', views.ApiTTSView.as_view(), name='api_tts'),
    path('api/translate/', views.ApiTranslateView.as_view(), name='api_translate'),
    path('api/dictionary/', views.ApiDictionaryView.as_view(), name='api_dictionary'),
]
