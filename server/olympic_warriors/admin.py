from django.contrib import admin
from .models import Player, Team, Edition, Discipline, Rugby, RugbyEvent, Game, GameEvent, Crossfit

admin.site.register(Player)
admin.site.register(Team)
admin.site.register(Edition)
admin.site.register(Discipline)
admin.site.register(Crossfit)
admin.site.register(Rugby)
admin.site.register(RugbyEvent)
admin.site.register(Game)
admin.site.register(GameEvent)
