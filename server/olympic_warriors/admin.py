"""
Admin dashboard configuration for the Olympic Warriors app.
"""

from django.contrib.admin import site, ModelAdmin, TabularInline
from django.http import HttpRequest
from .models import (
    Player,
    PlayerRating,
    Team,
    Edition,
    Discipline,
    TeamSportRound,
    Game,
    GameEvent,
    Rugby,
    RugbyEvent,
    Dodgeball,
    DodgeballEvent,
    Crossfit,
    HideAndSeek,
    Orienteering,
    Blindtest,
)


def request_only_active(request: HttpRequest) -> HttpRequest:
    """
    Filter the request to only show active items.
    """
    if not request.GET.get("is_active__exact"):
        q = request.GET.copy()
        q["is_active__exact"] = "1"
        request.GET = q
        request.META["QUERY_STRING"] = request.GET.urlencode()
    return request


class PlayerRatingInline(TabularInline):
    """
    Inline for the PlayerRating model to be accessed from the Player model.
    """

    model = PlayerRating
    extra = 1


class PlayerInline(TabularInline):
    """
    Inline for the Player model to be accessed from the Team model.
    """

    model = Player
    extra = 1


class PlayerAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the Player model.
    """

    list_display = ["user", "rating", "team", "edition"]
    list_filter = ["team", "edition", "is_active"]
    search_fields = ["name", "team", "user", "edition"]
    inlines = [PlayerRatingInline]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class PlayerRatingAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the PlayerRating model.
    """

    list_display = ["player", "name", "identifier", "rating"]
    list_filter = ["player__user", "name", "identifier", "player__edition", "is_active"]
    search_fields = ["player", "name", "identifier"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class TeamAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the Team model.
    """

    list_display = ["name", "edition"]
    list_filter = ["edition", "is_active"]
    search_fields = ["name", "edition"]
    inlines = [PlayerInline]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class EditionAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the Edition model.
    """

    list_display = ["year"]
    list_filter = ["is_active"]
    search_fields = ["year"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class DisciplineAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the Discipline model.
    """

    list_display = ["name", "edition"]
    list_filter = ["is_active", "edition", "name"]
    search_fields = ["name", "edition"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class TeamSportRoundAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the TeamSportRound model.
    """

    list_display = ["discipline", "order"]
    list_filter = ["discipline", "order"]
    search_fields = ["discipline", "order"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class GameAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the Game model.
    """

    list_display = [
        "discipline",
        "team1",
        "score1",
        "score2",
        "team2",
        "referees",
        "round",
        "edition",
    ]
    list_filter = ["discipline", "team1", "team2", "edition", "is_active"]
    search_fields = ["discipline", "team1", "team2", "edition"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class GameEventAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the GameEvent model.
    """

    list_display = ["game", "player1", "player2", "time"]
    list_filter = ["game", "player1", "player2", "is_active"]
    search_fields = ["game", "player1", "player2"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class RugbyEventAdmin(GameEventAdmin):
    """
    Admin dashboard configuration for the RugbyEvent model.
    """

    list_display = ["game", "player1", "player2", "time", "event_type"]
    list_filter = ["game", "player1", "player2", "event_type", "is_active"]
    search_fields = ["game", "player1", "player2", "event_type"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class DodgeballEventAdmin(GameEventAdmin):
    """
    Admin dashboard configuration for the DodgeballEvent model.
    """

    list_display = ["game", "player1", "player2", "time", "event_type"]
    list_filter = ["game", "player1", "player2", "event_type", "is_active"]
    search_fields = ["game", "player1", "player2", "event_type"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


site.register(Player, PlayerAdmin)
site.register(Team, TeamAdmin)
site.register(Edition, EditionAdmin)
site.register(PlayerRating, PlayerRatingAdmin)
site.register(Discipline, DisciplineAdmin)
site.register(TeamSportRound, TeamSportRoundAdmin)
site.register(Game, GameAdmin)
site.register(GameEvent, GameEventAdmin)
site.register(Crossfit, DisciplineAdmin)
site.register(Rugby, DisciplineAdmin)
site.register(RugbyEvent, RugbyEventAdmin)
site.register(Dodgeball, DisciplineAdmin)
site.register(DodgeballEvent, DodgeballEventAdmin)
site.register(HideAndSeek, DisciplineAdmin)
site.register(Orienteering, DisciplineAdmin)
site.register(Blindtest, DisciplineAdmin)
