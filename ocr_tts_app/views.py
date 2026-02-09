from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from datetime import datetime, timedelta
from django.utils import timezone
import json
from django.utils.safestring import mark_safe
import os
import sys
import time
import logging
import traceback
from PIL import Image
import json

from .models import LearningHistory, UserProfile
from .forms import ImageUploadForm, TextProcessingForm

# Compatibility alias
OCRTTSSession = LearningHistory

logger = logging.getLogger(__name__)

# Import dictionary service
try:
    sys.path.append(os.path.join(settings.BASE_DIR, 'services'))
    from dictionary_service import get_dictionary_service, lookup_word_definition
    DICTIONARY_AVAILABLE = True
    logger.info("✅ Dictionary service imported in views")
except ImportError as e:
    logger.warning(f"⚠️ Dictionary service not available in views: {e}")
    DICTIONARY_AVAILABLE = False

# Import OCR pipeline
sys.path.append(os.path.join(settings.BASE_DIR, 'src'))
try:
    from ocr_pipeline import get_ocr_pipeline
    logger.info("✅ OCR pipeline imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import OCR pipeline: {e}")
    get_ocr_pipeline = None

"""
Service imports (TTS, Translation, RAG)
These are loaded with graceful fallbacks so core OCR/TTS/Translation features
continue to work even if optional services are unavailable.
"""

# Import services
sys.path.append(os.path.join(settings.BASE_DIR, 'services'))
try:
    from tts_service import get_tts_service
    from translation_service import get_translation_service
except ImportError as e:
    logger.error(f"Failed to import services: {e}")
    # Fallback to src modules for backward compatibility
    sys.path.append(os.path.join(settings.BASE_DIR, 'src'))
    try:
        from tts_multilang import get_tts_instance as get_tts_service
        from translate import get_translator as get_translation_service
    except ImportError as e2:
        logger.error(f"Failed to import fallback modules: {e2}")
        get_tts_service = None
        get_translation_service = None

# Import RAG service (optional, non-fatal if unavailable)
try:
    from rag_service import get_rag_service
    RAG_AVAILABLE = True
    logger.info("✅ RAG service imported in views")
except ImportError as e:
    logger.warning(f"⚠️ RAG service not available in views: {e}")
    RAG_AVAILABLE = False

class HomeView(View):
    """Home page - public landing page"""
    
    def get(self, request):
        # Redirect to dashboard if user is logged in
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        # Show public home page for anonymous users
        context = {
            'platform_name': 'Learnify',
            'supported_languages': getattr(settings, 'SUPPORTED_LANGUAGES', []),
        }
        return render(request, 'ocr_tts_app/home.html', context)

class DashboardView(LoginRequiredMixin, View):
    """User dashboard showing learning history and statistics"""
    
    def get(self, request):
        user = request.user
        
        # Ensure user has a profile
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)
        
        # Get user's learning sessions
        sessions = LearningHistory.objects.filter(user=user).order_by('-created_at')
        
        # Calculate statistics
        total_sessions = sessions.count()
        completed_sessions = sessions.filter(ocr_status='completed').count()
        favorite_sessions = sessions.filter(is_favorited=True)
        
        # Recent activity (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_sessions = sessions.filter(created_at__gte=week_ago)
        
        # Group sessions by learning type
        session_types = sessions.values('learning_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent sessions for display
        recent_display_sessions = sessions[:10]
        
        # Chart data for analytics
        chart_data = self._get_chart_data(user, sessions)
        feature_usage = self._get_feature_usage(sessions)
        
        context = {
            'profile': profile,
            'sessions': recent_display_sessions,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'favorite_sessions': favorite_sessions[:5],
            'recent_sessions_count': recent_sessions.count(),
            'session_types': session_types,
            'chart_data': chart_data,
            'feature_usage': feature_usage,
            'stats': {
                'total_sessions': total_sessions,
                'completed_sessions': completed_sessions,
                'success_rate': (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                'favorite_count': favorite_sessions.count(),
                'recent_count': recent_sessions.count(),
            }
        }
        
        return render(request, 'ocr_tts_app/dashboard.html', context)
    
    def _get_chart_data(self, user, sessions):
        """Generate chart data for the last 7 days (timezone-aware)"""
        # Initialize data arrays
        labels = []
        ocr_data = []              # image_ocr
        tts_data = []              # text_input (direct TTS)

        # Use local date for the user's timezone
        today_local = timezone.localdate()

        # Build last 7 days labels and counts (chronological)
        for i in range(6, -1, -1):  # 6, 5, 4, 3, 2, 1, 0
            day = today_local - timedelta(days=i)
            labels.append(day.strftime('%d/%m'))
            day_sessions = sessions.filter(created_at__date=day)

            ocr_count = day_sessions.filter(learning_type='image_ocr').count()
            tts_count = day_sessions.filter(learning_type='text_input').count()
            ocr_data.append(ocr_count)
            tts_data.append(tts_count)

        # Prepare JS-friendly JSON arrays
        return {
            'labels': mark_safe(json.dumps(labels)),
            'ocr_sessions': mark_safe(json.dumps(ocr_data)),
            'tts_sessions': mark_safe(json.dumps(tts_data))
        }
    
    def _get_feature_usage(self, sessions):
        """Calculate feature usage percentages (OCR, TTS, Dictionary). Translation removed."""
        if not sessions.exists():
            return {'ocr': 0, 'tts': 0, 'dictionary': 0}
        
        total = sessions.count()
        ocr_count = sessions.filter(learning_type='image_ocr').count()
        tts_count = sessions.filter(learning_type='text_input').count()
        dictionary_count = sessions.filter(is_single_word=True).count()
        
        # Normalize to percentages (exclude translation from distribution)
        denom = total if total > 0 else 1
        return {
            'ocr': round((ocr_count / denom) * 100),
            'tts': round((tts_count / denom) * 100),
            'dictionary': round((dictionary_count / denom) * 100),
        }

class UploadView(LoginRequiredMixin, View):
    """Display upload form for authenticated users"""
    
    def get(self, request):
        form = ImageUploadForm()
        # Get user's recent sessions
        recent_sessions = LearningHistory.objects.filter(
            user=request.user,
            ocr_status='completed'
        ).order_by('-created_at')[:5]
        
        return render(request, 'ocr_tts_app/ocr_upload.html', {
            'form': form,
            'recent_sessions': recent_sessions
        })

class UploadImageView(LoginRequiredMixin, View):
    """Handle image upload and processing"""
    
    def post(self, request):
        form = ImageUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Check if image file was uploaded
                if 'uploaded_image' not in request.FILES:
                    messages.error(request, "Please select an image file to upload.")
                    return render(request, 'ocr_tts_app/ocr_upload.html', {'form': form})
                
                # Create new session associated with user
                session = LearningHistory.objects.create(
                    user=request.user,
                    learning_type='image_ocr'
                )
                
                # Save uploaded image
                uploaded_file = request.FILES['uploaded_image']
                session.uploaded_image = uploaded_file
                session.image_filename = uploaded_file.name
                session.save()
                
                # Process OCR with trained model
                logger.info(f"🔍 Starting OCR processing for {uploaded_file.name}")
                try:
                    start_ocr = time.time()
                    
                    if get_ocr_pipeline is None:
                        raise RuntimeError('OCR pipeline not available')
                    
                    # Get OCR pipeline instance (cached)
                    ocr_pipeline = get_ocr_pipeline()
                    
                    # Extract text from uploaded image
                    session.ocr_status = 'processing'
                    session.save(update_fields=['ocr_status'])
                    
                    # Use the uploaded image file path
                    image_path = session.uploaded_image.path
                    
                    # Get user's target language for dictionary lookup
                    user_language = getattr(session.user.profile, 'target_language', 'en')
                    
                    # Extract text with dictionary lookup
                    ocr_result = ocr_pipeline.extract_text(image_path, language=user_language, include_dictionary=True)
                    
                    # Handle both old string format and new dict format for compatibility
                    if isinstance(ocr_result, dict):
                        extracted_text = ocr_result.get('text', '')
                        session.is_single_word = ocr_result.get('is_single_word', False)
                        session.word_definitions = ocr_result.get('word_definitions', [])
                        session.dictionary_status = ocr_result.get('dictionary_status', 'pending')
                    else:
                        # Backward compatibility for old string format
                        extracted_text = str(ocr_result)
                        session.is_single_word = False
                        session.word_definitions = []
                        session.dictionary_status = 'disabled'
                    
                    # Save OCR results
                    session.extracted_text = extracted_text
                    session.ocr_status = 'completed'
                    session.word_count = len(extracted_text.split()) if extracted_text else 0
                    session.processing_time_ocr = round(time.time() - start_ocr, 3)
                    session.save()

                    logger.info(f"✅ OCR completed in {session.processing_time_ocr}s. Extracted {len(extracted_text)} characters")

                    # Index session for RAG (non-blocking best-effort)
                    if RAG_AVAILABLE:
                        try:
                            rag_service = get_rag_service()
                            rag_service.index_learning_session(
                                session_id=session.id,
                                user=request.user,
                                extracted_text=session.extracted_text,
                                word_definitions=session.word_definitions,
                                is_single_word=session.is_single_word,
                            )
                            logger.info("🧠 Session indexed for RAG (session_id=%s)", session.session_id)
                        except Exception as rag_err:
                            logger.warning("⚠️ RAG indexing failed for session %s: %s", session.session_id, rag_err)

                    # Log dictionary results if available
                    if session.is_single_word and session.word_definitions:
                        logger.info(f"📚 Dictionary lookup found {len(session.word_definitions)} definitions for '{extracted_text}'")
                    elif session.is_single_word:
                        logger.info(f"📖 No dictionary definitions found for single word '{extracted_text}'")
                    else:
                        logger.info("📖 Multiple words detected, dictionary lookup skipped")
                    
                except Exception as ocr_err:
                    logger.error(f"❌ OCR processing failed: {ocr_err}")
                    session.ocr_status = 'failed'
                    session.ocr_error = str(ocr_err)
                    session.extracted_text = f"OCR processing failed: {str(ocr_err)}"
                    session.save(update_fields=['ocr_status', 'ocr_error', 'extracted_text'])
                    
                    # Don't proceed to TTS if OCR failed
                    messages.error(request, f"OCR processing failed: {str(ocr_err)}")
                    return redirect('result', session_id=session.session_id)
                
                # Update user profile statistics
                profile = request.user.profile
                profile.total_sessions += 1
                profile.save()
                
                # Run TTS immediately using the services layer
                language = getattr(getattr(request.user, 'profile', None), 'target_language', getattr(settings, 'DEFAULT_TARGET_LANGUAGE', 'en'))
                logger.info(f"🎙️ Starting TTS processing for extracted text")
                try:
                    start_tts = time.time()
                    
                    if get_tts_service is None:
                        raise RuntimeError('TTS service not available')
                    
                    tts_service = get_tts_service()
                    
                    # Get user's voice preference from profile
                    voice_preference = getattr(getattr(request.user, 'profile', None), 'voice_preference', 'female')
                    voice = 'female' if voice_preference in ['female', 'neutral'] else 'male'
                    
                    # Set TTS processing status
                    session.tts_status = 'processing'
                    session.save(update_fields=['tts_status'])
                    
                    # Use fixed 0.5x speed for clarity (as specified in requirements)
                    abs_path, audio_url = tts_service.synthesize(session.extracted_text, language, voice, 0.5)

                    # Persist result
                    session.tts_status = 'completed'
                    # Store relative path for compatibility (e.g. 'media/tts/xxx.wav')
                    session.audio_file_path = audio_url.lstrip('/')
                    session.processing_time_tts = round(time.time() - start_tts, 3)
                    session.save()
                    
                    logger.info(f"✅ TTS completed in {session.processing_time_tts}s. Audio saved at: {audio_url}")
                    
                except Exception as tts_err:
                    logger.error(f"❌ TTS generation failed: {tts_err}")
                    session.tts_status = 'failed'
                    session.tts_error = str(tts_err)
                    session.save(update_fields=['tts_status', 'tts_error'])
                    # Continue to show results even if TTS failed
                
                messages.success(request, "Image uploaded and processed successfully!")
                return redirect('result', session_id=session.session_id)
                
            except Exception as e:
                logger.error(f"Upload processing failed: {e}")
                logger.error(traceback.format_exc())
                messages.error(request, f"Processing failed: {str(e)}")
                
        else:
            messages.error(request, "Please upload a valid image file.")
        
        # If we get here, there was an error
        recent_sessions = LearningHistory.objects.filter(
            user=request.user,
            ocr_status='completed'
        ).order_by('-created_at')[:5]
        
        return render(request, 'ocr_tts_app/ocr_upload.html', {
            'form': form,
            'recent_sessions': recent_sessions
        })
    
    # TODO: Implement these methods after model training is complete
    # def _process_ocr(self, session):
    #     """Process OCR for the session"""
    #     pass
    
    # def _process_tts(self, session):
    #     """Process TTS for the session"""
    #     pass

class ResultView(LoginRequiredMixin, View):
    """Display processing results"""
    
    def get(self, request, session_id):
        # Ensure user can only view their own sessions
        session = get_object_or_404(
            LearningHistory, 
            session_id=session_id, 
            user=request.user
        )
        
        return render(request, 'ocr_tts_app/result.html', {
            'session': session
        })

class SessionListView(LoginRequiredMixin, View):
    """List user's processing sessions"""
    
    def get(self, request):
        sessions = LearningHistory.objects.filter(
            user=request.user
        ).order_by('-created_at')
        
        return render(request, 'ocr_tts_app/session_list.html', {
            'sessions': sessions
        })

class DeleteSessionView(LoginRequiredMixin, View):
    """Delete a single session belonging to the current user (POST only)."""
    def post(self, request, session_id):
        try:
            session = get_object_or_404(LearningHistory, session_id=session_id, user=request.user)

            # Attempt to delete associated files (image and audio)
            try:
                # Delete uploaded image file if exists
                if session.uploaded_image and hasattr(session.uploaded_image, 'path'):
                    image_path = session.uploaded_image.path
                    if os.path.isfile(image_path):
                        os.remove(image_path)
                # Delete audio file if stored as file field
                if session.audio_file and hasattr(session.audio_file, 'path'):
                    audio_path_abs = session.audio_file.path
                    if os.path.isfile(audio_path_abs):
                        os.remove(audio_path_abs)
                # Delete audio path if stored as path string (backward compatibility)
                if session.audio_file_path:
                    possible_path = session.audio_file_path
                    if possible_path.startswith('/'):
                        possible_path = possible_path[1:]
                    # Build absolute path under MEDIA_ROOT
                    abs_path = os.path.join(settings.BASE_DIR, possible_path)
                    if not os.path.isabs(abs_path):
                        abs_path = os.path.join(settings.BASE_DIR, possible_path)
                    # Also try MEDIA_ROOT join
                    media_candidate = os.path.join(settings.MEDIA_ROOT, os.path.basename(possible_path))
                    for candidate in [abs_path, media_candidate]:
                        try:
                            if os.path.isfile(candidate):
                                os.remove(candidate)
                        except Exception:
                            pass
            except Exception:
                # File deletion failures should not block history deletion
                logger.warning("Failed to delete one or more files for session %s", session.session_id)

            session.delete()
            messages.success(request, "Session deleted successfully.")
        except Exception as e:
            logger.error("Failed to delete session: %s", e)
            messages.error(request, f"Failed to delete session: {str(e)}")
        return redirect('session_list')

class DeleteAllSessionsView(LoginRequiredMixin, View):
    """Delete all sessions for the current user (POST only)."""
    def post(self, request):
        try:
            sessions = LearningHistory.objects.filter(user=request.user)
            # Best-effort file cleanup
            for session in sessions:
                try:
                    if session.uploaded_image and hasattr(session.uploaded_image, 'path'):
                        if os.path.isfile(session.uploaded_image.path):
                            os.remove(session.uploaded_image.path)
                    if session.audio_file and hasattr(session.audio_file, 'path'):
                        if os.path.isfile(session.audio_file.path):
                            os.remove(session.audio_file.path)
                    if session.audio_file_path:
                        pp = session.audio_file_path.lstrip('/')
                        candidates = [
                            os.path.join(settings.BASE_DIR, pp),
                            os.path.join(settings.MEDIA_ROOT, os.path.basename(pp)),
                        ]
                        for c in candidates:
                            try:
                                if os.path.isfile(c):
                                    os.remove(c)
                            except Exception:
                                pass
                except Exception:
                    pass
            sessions.delete()
            messages.success(request, "All sessions deleted successfully.")
        except Exception as e:
            logger.error("Failed to delete all sessions: %s", e)
            messages.error(request, f"Failed to delete all sessions: {str(e)}")
        return redirect('session_list')

class TextToSpeechView(LoginRequiredMixin, View):
    """Handle direct text to speech conversion"""
    
    def get(self, request):
        form = TextProcessingForm()
        
        # Get user's voice preference
        try:
            user_profile = request.user.profile
            user_voice_preference = user_profile.voice_preference
        except:
            user_voice_preference = 'female'  # Default fallback
            
        return render(request, 'ocr_tts_app/text_to_speech.html', {
            'form': form,
            'user_voice_preference': user_voice_preference
        })
    
    def post(self, request):
        form = TextProcessingForm(request.POST)
        
        if form.is_valid():
            try:
                # Create new session for text processing
                session = LearningHistory.objects.create(
                    user=request.user,
                    learning_type='text_input'
                )
                session.extracted_text = form.cleaned_data['text']
                session.ocr_status = 'completed'  # Skip OCR since we have text
                session.word_count = len(session.extracted_text.split())
                session.save()

                # Index session for RAG (non-blocking best-effort)
                if RAG_AVAILABLE:
                    try:
                        rag_service = get_rag_service()
                        rag_service.index_learning_session(
                            session_id=session.id,
                            user=request.user,
                            extracted_text=session.extracted_text,
                            word_definitions=session.word_definitions if hasattr(session, "word_definitions") else None,
                            is_single_word=getattr(session, "is_single_word", False),
                        )
                        logger.info("🧠 Text-input session indexed for RAG (session_id=%s)", session.session_id)
                    except Exception as rag_err:
                        logger.warning("⚠️ RAG indexing failed for text-input session %s: %s", session.session_id, rag_err)

                # Update user profile statistics
                profile = request.user.profile
                profile.total_sessions += 1
                profile.save()
                
                # Run TTS immediately using the services layer
                language = getattr(getattr(request.user, 'profile', None), 'target_language', getattr(settings, 'DEFAULT_TARGET_LANGUAGE', 'en'))
                try:
                    start_tts = time.time()
                    if get_tts_service is None:
                        raise RuntimeError('TTS service not available')
                    tts_service = get_tts_service()
                    # Get selected voice from form (if available) or user's profile preference
                    selected_voice = request.POST.get('voice_selection', None)
                    if not selected_voice:
                        # Fallback to user's profile preference
                        voice_preference = getattr(getattr(request.user, 'profile', None), 'voice_preference', 'female')
                        selected_voice = voice_preference
                    
                    # Speed is fixed at 0.5x for clarity
                    speed = 0.5
                    
                    # Map neutral to female for now (since our TTS service supports male/female)
                    voice = 'female' if selected_voice in ['female', 'neutral'] else 'male'
                    
                    # Use enhanced interface with voice and speed support
                    abs_path, audio_url = tts_service.synthesize(session.extracted_text, language, voice, speed)

                    session.tts_status = 'completed'
                    session.audio_file_path = audio_url.lstrip('/')
                    session.processing_time_tts = round(time.time() - start_tts, 3)
                    session.save()
                except Exception as tts_err:
                    logger.error(f"TTS generation failed: {tts_err}")
                    session.tts_status = 'failed'
                    session.tts_error = str(tts_err)
                    session.save(update_fields=['tts_status', 'tts_error'])
                
                messages.success(request, "Text submitted for processing!")
                return redirect('result', session_id=session.session_id)
                
            except Exception as e:
                logger.error(f"Text processing failed: {e}")
                messages.error(request, f"Processing failed: {str(e)}")
        
        return render(request, 'ocr_tts_app/text_to_speech.html', {
            'form': form
        })

class TranslationView(LoginRequiredMixin, View):
    """Handle translation interface"""
    
    def get(self, request):
        context = {
            'supported_languages': [
                ('en', 'English'),
                ('zh', 'Chinese'),
                ('ms', 'Malay'),
            ]
        }
        return render(request, 'ocr_tts_app/translation.html', context)

@method_decorator(csrf_exempt, name='dispatch')
class ProcessingStatusView(View):
    """API endpoint to check processing status"""
    
    def get(self, request, session_id):
        try:
            session = get_object_or_404(LearningHistory, session_id=session_id, user=request.user)
            
            data = {
                'session_id': str(session.session_id),
                'ocr_status': session.ocr_status,
                'tts_status': session.tts_status,
                'extracted_text': session.extracted_text,
                'audio_url': session.audio_url,
                'is_completed': session.is_completed,
                'has_errors': session.has_errors,
                'ocr_error': session.ocr_error,
                'tts_error': session.tts_error,
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class ApiTTSView(View):
    """POST /api/tts/ { text: str, language: en|zh|ms, voice: male|female, speed: 0.5-2.0 } -> { audio_url }"""
    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
            text = payload.get('text', '').strip()
            language = payload.get('language', 'en').lower()
            voice = payload.get('voice', 'female').lower()
            speed = payload.get('speed', 1.0)
            
            # Validate inputs
            if not text:
                return JsonResponse({'error': 'Text is required'}, status=400)
            if language not in {'en','zh','ms'}:
                return JsonResponse({'error': 'language must be one of en, zh, ms'}, status=400)
            if voice not in {'male', 'female', 'neutral'}:
                return JsonResponse({'error': 'voice must be male, female, or neutral'}, status=400)
            
            # Speed is fixed at 0.5x for clarity
            speed = 0.5

            if get_tts_service is None:
                return JsonResponse({'error': 'TTS service not available'}, status=503)

            tts_service = get_tts_service()
            
            # Map neutral to female for TTS service (since our TTS service supports male/female)
            actual_voice = 'female' if voice == 'neutral' else voice
            
            # Use enhanced interface with voice and speed support
            abs_path, audio_url = tts_service.synthesize(text, language, actual_voice, speed)
            
            return JsonResponse({
                'audio_url': audio_url,
                'language': language,
                'voice': voice,
                'speed': speed,
                'message': 'TTS synthesis successful'
            })
            
        except ValueError as e:
            logger.warning(f"/api/tts validation error: {e}")
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.exception("/api/tts error")
            return JsonResponse({'error': f'TTS synthesis failed: {str(e)}'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ApiTranslateView(View):
    """POST /api/translate/ { text, source_lang, target_lang } -> { translated_text }"""
    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
            text = payload.get('text', '').strip()
            source_lang = payload.get('source_lang', 'en').lower()
            target_lang = payload.get('target_lang', 'en').lower()
            
            if not text:
                return JsonResponse({'error': 'Text is required'}, status=400)
            
            for v in (source_lang, target_lang):
                if v not in {'en','zh','ms'}:
                    return JsonResponse({'error': 'Languages must be one of en, zh, ms'}, status=400)

            if get_translation_service is None:
                return JsonResponse({'error': 'Translation service not available'}, status=503)

            translation_service = get_translation_service()
            
            # Handle both old and new service interfaces
            if hasattr(translation_service, 'translate'):
                translated = translation_service.translate(text, source_lang, target_lang)
            else:
                # Fallback for old interface
                translated = translation_service.translate(text, source_lang, target_lang)
            
            return JsonResponse({
                'translated_text': translated,
                'source_lang': source_lang,
                'target_lang': target_lang,
                'message': 'Translation successful'
            })
            
        except ValueError as e:
            logger.warning(f"/api/translate validation error: {e}")
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.exception("/api/translate error")
            return JsonResponse({'error': f'Translation failed: {str(e)}'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ApiDictionaryView(View):
    """POST /api/dictionary/ { word, language } -> { is_single_word, definitions }"""
    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
            word = payload.get('word', '').strip()
            language = payload.get('language', 'en').lower()
            
            if not word:
                return JsonResponse({'error': 'Word parameter is required'}, status=400)
            
            if not DICTIONARY_AVAILABLE:
                return JsonResponse({'error': 'Dictionary service not available'}, status=503)
            
            # Validate language
            if language not in ['en', 'zh', 'ms']:
                return JsonResponse({'error': 'Unsupported language. Use: en, zh, ms'}, status=400)
            
            logger.info(f"📖 Dictionary lookup request: word='{word}', language='{language}'")
            
            # Perform dictionary lookup
            is_single_word, definitions = lookup_word_definition(word, language)
            
            if not is_single_word:
                return JsonResponse({
                    'is_single_word': False,
                    'definitions': [],
                    'message': 'Text contains multiple words or invalid format'
                })
            
            return JsonResponse({
                'is_single_word': True,
                'definitions': definitions,
                'word': word,
                'language': language,
                'count': len(definitions)
            })
            
        except ValueError as e:
            logger.warning(f"/api/dictionary validation error: {e}")
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.exception("/api/dictionary error")
            return JsonResponse({'error': f'Dictionary lookup failed: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ApiRAGExplainView(LoginRequiredMixin, View):
    """
    POST /api/rag/explain/
    Payload: { "question": str, "session_id": str (optional) }
    Response: { "answer": str, "sources": [...]} or error
    """

    def post(self, request):
        if not RAG_AVAILABLE:
            return JsonResponse({'error': 'RAG service not available'}, status=503)

        try:
            payload = json.loads(request.body.decode('utf-8'))
            question = (payload.get('question') or '').strip()
            session_id = payload.get('session_id')

            if not question:
                return JsonResponse({'error': 'Question is required'}, status=400)

            rag_service = get_rag_service()

            answer, sources = rag_service.answer_question(
                user=request.user,
                question=question,
                session_id=session_id,
            )

            return JsonResponse(
                {
                    'answer': answer,
                    'sources': sources,
                }
            )
        except ValueError as e:
            logger.warning(f"/api/rag/explain validation error: {e}")
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.exception("/api/rag/explain error")
            return JsonResponse({'error': f'RAG explanation failed: {str(e)}'}, status=500)

class ExportLearningNoteView(LoginRequiredMixin, View):
    """Export learning session as a formatted text file"""
    
    def get(self, request, session_id):
        try:
            session = get_object_or_404(LearningHistory, session_id=session_id, user=request.user)
            
            # Generate the learning note content
            content = self._generate_learning_note(session, request.user)
            
            # Create the filename
            safe_text = "".join(c for c in session.extracted_text[:20] if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_text:
                safe_text = "learning_note"
            filename = f"{safe_text}_{session.created_at.strftime('%Y%m%d_%H%M%S')}.txt"
            
            # Create HTTP response with file download
            response = HttpResponse(content, content_type='text/plain; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"📄 Learning note exported: {filename} for session {session.session_id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Export learning note failed: {e}")
            messages.error(request, f"Failed to export learning note: {str(e)}")
            return redirect('result', session_id=session_id)
    
    def _generate_learning_note(self, session, user):
        """Generate formatted learning note content"""
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("📚 LANGUAGE LEARNING NOTE")
        lines.append("=" * 60)
        lines.append("")
        
        # Session info
        lines.append(f"📅 Date: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"👤 User: {user.get_full_name() or user.username}")
        user_lang = getattr(session.user.profile, 'target_language', 'en')
        lang_names = {'en': 'English', 'zh': 'Chinese', 'ms': 'Malay'}
        lines.append(f"🌐 Language: {lang_names.get(user_lang, 'English')}")
        lines.append(f"📝 Session ID: {session.session_id}")
        lines.append("")
        
        # Recognized text
        lines.append("🔍 RECOGNIZED TEXT")
        lines.append("-" * 30)
        if session.extracted_text:
            lines.append(f'"{session.extracted_text}"')
            lines.append("")
            if session.word_count:
                lines.append(f"Word count: {session.word_count}")
            if session.processing_time_ocr:
                lines.append(f"OCR processing time: {session.processing_time_ocr:.2f} seconds")
        else:
            lines.append("No text was recognized.")
        lines.append("")
        
        # Dictionary definitions (if single word)
        if session.is_single_word and session.word_definitions:
            lines.append("📖 DICTIONARY DEFINITIONS")
            lines.append("-" * 30)
            lines.append(f'Word: "{session.extracted_text}"')
            lines.append("")
            
            for i, definition in enumerate(session.word_definitions, 1):
                lines.append(f"{i}. {definition.get('part_of_speech', '').upper()}")
                lines.append(f"   Definition: {definition.get('definition', 'No definition available')}")
                
                if definition.get('example'):
                    lines.append(f"   Example: \"{definition['example']}\"")
                
                if definition.get('pronunciation'):
                    lines.append(f"   Pronunciation: {definition['pronunciation']}")
                
                lines.append("")
            
        elif session.is_single_word:
            lines.append("📖 DICTIONARY LOOKUP")
            lines.append("-" * 30)
            if session.dictionary_status == 'completed':
                lines.append(f'No definitions found for "{session.extracted_text}"')
            elif session.dictionary_status == 'failed':
                lines.append(f'Dictionary lookup failed for "{session.extracted_text}"')
            else:
                lines.append(f'Dictionary lookup was not completed for "{session.extracted_text}"')
            lines.append("")
        
        # Translations (if available)
        translations = self._get_translations(session)
        if translations:
            lines.append("🌍 TRANSLATIONS")
            lines.append("-" * 30)
            for lang_code, translation in translations.items():
                lang_name = {'en': 'English', 'zh': 'Chinese', 'ms': 'Malay'}.get(lang_code, lang_code)
                lines.append(f"{lang_name}: {translation}")
            lines.append("")
        
        # Learning progress
        if session.times_played > 0:
            lines.append("📊 LEARNING PROGRESS")
            lines.append("-" * 30)
            lines.append(f"Times reviewed: {session.times_played}")
            if session.last_played_at:
                lines.append(f"Last reviewed: {session.last_played_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if session.is_favorited:
                lines.append("⭐ Marked as favorite")
            lines.append("")
        
        # Learning suggestions
        if session.is_single_word and session.word_definitions:
            lines.append("💡 LEARNING SUGGESTIONS")
            lines.append("-" * 30)
            lines.append("• Try using this word in your own sentences")
            lines.append("• Look for this word in other texts to see different contexts")
            lines.append("• Practice writing the word multiple times")
            if len(session.word_definitions) > 1:
                lines.append("• Notice how this word has multiple meanings - context matters!")
            lines.append("")
        
        # Footer
        lines.append("=" * 60)
        lines.append("Generated by Online Language Learning System")
        lines.append(f"Export time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _get_translations(self, session):
        """Get translations for the recognized text if available"""
        translations = {}
        
        if not session.extracted_text or not get_translation_service:
            return translations
        
        try:
            # Get user's target language
            user_lang = getattr(session.user.profile, 'target_language', 'en')
            
            # Define languages to translate to
            supported_languages = ['en', 'zh', 'ms']
            languages_to_translate = [lang for lang in supported_languages if lang != user_lang]
            
            # Only translate single words or short phrases (to avoid API overuse)
            if session.word_count and session.word_count <= 3:
                translation_service = get_translation_service()
                
                for target_lang in languages_to_translate:
                    try:
                        translated = translation_service.translate(
                            session.extracted_text, 
                            source_lang=user_lang, 
                            target_lang=target_lang
                        )
                        if translated and translated.lower() != session.extracted_text.lower():
                            translations[target_lang] = translated
                    except Exception as e:
                        logger.warning(f"Translation failed for {target_lang}: {e}")
                        
        except Exception as e:
            logger.warning(f"Translation service error: {e}")
        
        return translations
