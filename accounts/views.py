from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
import logging

from .forms import CustomUserCreationForm, CustomLoginForm, UserProfileForm
from ocr_tts_app.models import UserProfile

logger = logging.getLogger(__name__)

class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    # Send a plain-text body plus an HTML alternative to ensure proper rendering in inboxes
    email_template_name = 'accounts/password_reset_email.txt'
    html_email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def get_email_context(self, context):
        """Inject an absolute reset_url built from the current request host.
        This avoids localhost/127.0.0.1 issues when opening the email on another device.
        """
        from django.urls import reverse

        request = getattr(self, 'request', None)
        uidb64 = context.get('uid')
        token = context.get('token')

        if request and uidb64 and token:
            reset_path = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
            reset_url = request.build_absolute_uri(reset_path)
            context['reset_url'] = reset_url

        # Friendly site name
        context.setdefault('site_name', 'Learnify')
        return context

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'

def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create user
                    user = form.save()
                    
                    # UserProfile is automatically created by the signal
                    # Now update it with the user's preferences
                    try:
                        profile = user.profile
                        profile.target_language = form.cleaned_data.get('target_language', 'en')
                        profile.voice_preference = form.cleaned_data.get('voice_preference', 'female')
                        profile.save()
                    except UserProfile.DoesNotExist:
                        # Fallback if signal didn't work
                        UserProfile.objects.create(
                            user=user,
                            target_language=form.cleaned_data.get('target_language', 'en'),
                            voice_preference=form.cleaned_data.get('voice_preference', 'female')
                        )
                    
                    # Log the user in
                    username = form.cleaned_data.get('username')
                    password = form.cleaned_data.get('password1')
                    user = authenticate(username=username, password=password)
                    if user:
                        login(request, user)
                        messages.success(request, f'Welcome to Language Learning Hub, {user.first_name or user.username}!')
                        return redirect('dashboard')
                    
            except Exception as e:
                logger.error(f"Registration error: {e}")
                messages.error(request, 'There was an error creating your account. Please try again.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                
                # Redirect to next URL if provided, otherwise to dashboard
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    """User logout view"""
    username = request.user.username if request.user.is_authenticated else None
    logout(request)
    if username:
        messages.success(request, f'Goodbye, {username}! You have been logged out.')
    return redirect('home')

@login_required
def profile_view(request):
    """User profile view and editing"""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Update user fields
                    user = request.user
                    user.first_name = form.cleaned_data['first_name']
                    user.last_name = form.cleaned_data['last_name']
                    user.email = form.cleaned_data['email']
                    user.save()
                    
                    # Update profile
                    profile = form.save()
                    
                    messages.success(request, 'Your profile has been updated successfully!')
                    return redirect('accounts:profile')
            except Exception as e:
                logger.error(f"Profile update error: {e}")
                messages.error(request, 'There was an error updating your profile. Please try again.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        }
        form = UserProfileForm(instance=profile, initial=initial_data, user=request.user)
    
    # Get user statistics
    from ocr_tts_app.models import LearningHistory, LearningStatistics
    from django.db.models import Count, Sum
    from datetime import datetime, timedelta
    
    # Calculate statistics
    total_sessions = LearningHistory.objects.filter(user=request.user).count()
    completed_sessions = LearningHistory.objects.filter(
        user=request.user, 
        ocr_status='completed'
    ).count()
    
    # Get recent activity (last 7 days)
    week_ago = datetime.now() - timedelta(days=7)
    recent_sessions = LearningHistory.objects.filter(
        user=request.user,
        created_at__gte=week_ago
    ).count()
    
    # Get favorite sessions
    favorite_sessions = LearningHistory.objects.filter(
        user=request.user,
        is_favorited=True
    ).order_by('-created_at')[:5]
    
    context = {
        'form': form,
        'profile': profile,
        'stats': {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'recent_sessions': recent_sessions,
            'learning_streak': profile.learning_streak,
            'total_words_learned': profile.total_words_learned,
        },
        'favorite_sessions': favorite_sessions,
    }
    
    return render(request, 'accounts/profile.html', context)