from django.apps import AppConfig


class OlympicWarriorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'olympic_warriors'  # Replace 'your_app' with the name of your app

    def ready(self):
        # Import the signals here
        import olympic_warriors.signals  # Make sure to replace with your actual app name
