from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Create tokens for all existing users'

    def handle(self, *args, **kwargs):
        User = get_user_model()

        for user in User.objects.all():
            _, created = Token.objects.get_or_create(user=user)
            if created:
                self.stdout.write(f"Created token for user {user.username}")
            else:
                self.stdout.write(f"Token already exists for user {user.username}")

        self.stdout.write(self.style.SUCCESS('Successfully created tokens for all users'))
