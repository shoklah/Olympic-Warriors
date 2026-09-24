from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from .avatars import delete_on_commit, photo_names
from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


@receiver(post_delete, sender=UserProfile)
def delete_photo_files(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    A deleted profile takes its photo files with it, once the deletion commits: nginx
    serves them to anyone holding the URL, and erasing a person (their User, whose cascade
    deletes the profile, or the profile alone) must take their face down. A rolled-back
    deletion keeps them.
    """
    delete_on_commit(photo_names(instance))
