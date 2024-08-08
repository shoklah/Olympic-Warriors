"""
Creates a superuser for dev environment.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from olympic_warriors.settings import settings


class Command(BaseCommand):
    """
    Creates a superuser for dev environment.
    """

    help = "Creates a superuser."

    def handle(self, *args, **options):
        if not User.objects.filter(username=settings.SU_USERNAME).exists():
            User.objects.create_superuser(
                username=settings.SU_USERNAME, password=settings.SU_PASSWORD
            )
        print("Superuser has been created.")
