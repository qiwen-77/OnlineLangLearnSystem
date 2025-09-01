from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from ocr_tts_app.models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created"""
    if created:
        # Create UserProfile with default values
        UserProfile.objects.create(
            user=instance,
            target_language='en',  # Default to English
            voice_preference='female'  # Default to female voice
        )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is saved"""
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
