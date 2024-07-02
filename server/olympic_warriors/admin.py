from django.contrib import admin
from .models import Player, Team, Edition, Registration

admin.site.register(Player)
admin.site.register(Team)
admin.site.register(Edition)
admin.site.register(Registration)
