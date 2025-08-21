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
    TeamResult,
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
    BlindtestRound,
    BlindtestGuess,
    Petanque,
    Basketball,
    GeographyQuizz,
    Relay,
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


class BlindtestGuessInline(TabularInline):
    """
    Inline for the BlindtestGuess model to be accessed from the Blindtest model.
    """

    model = BlindtestGuess
    extra = 1


class BlindtestRoundInline(TabularInline):
    """
    Inline for the BlindtestRound model to be accessed from the Blindtest model.
    """

    model = BlindtestRound
    extra = 1

    inlines = [BlindtestGuessInline]


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


class RugbyEventInline(TabularInline):
    """
    Inline for the RugbyEvent model to be accessed from the Rugby model.
    """

    model = RugbyEvent
    extra = 1


class DodgeballEventInline(TabularInline):
    """
    Inline for the DodgeballEvent model to be accessed from the Dodgeball model.
    """

    model = DodgeballEvent
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

    list_display = ["name", "edition", "total_points", "ranking"]
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

    readonly_fields = ["name", "result_type"]
    list_display = ["name", "edition", "reveal_score"]
    list_filter = ["is_active", "edition", "name"]
    search_fields = ["name", "edition"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class BlindtestAdmin(DisciplineAdmin):
    """
    Admin dashboard configuration for the Blindtest model.
    """

    inlines = [BlindtestRoundInline]


class BlindtestGuessAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the BlindtestGuess model.
    """

    list_display = [
        "team",
        "blindtest_round",
        "artist",
        "song",
        "is_artist_correct",
        "is_song_correct",
    ]
    list_filter = ["team", "blindtest_round", "is_artist_correct", "is_song_correct", "is_active"]
    search_fields = ["team", "blindtest_round", "artist", "song"]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class BlindtestRoundAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the BlindtestRound model.
    """

    list_display = ["blindtest", "order", "is_active"]
    list_filter = ["blindtest", "order", "is_active"]
    search_fields = ["blindtest", "order"]

    inlines = [BlindtestGuessInline]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class TeamResultAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the TeamResult model.
    """

    list_display = [
        "team",
        "discipline",
        "result_type",
        "points",
        "time",
        "ranking",
        "global_points",
    ]
    list_filter = ["team", "discipline", "is_active"]
    search_fields = ["team", "discipline"]

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

    def get_inline_instances(self, request: HttpRequest, obj=None):
        """
        Display the right inline model admin according to the discipline
        """
        inlines = []
        if obj and obj.discipline:
            if obj.discipline.name == "Rugby":
                inlines.append(RugbyEventInline)
            elif obj.discipline.name == "Dodgeball":
                inlines.append(DodgeballEventInline)

        return [inline(self.model, self.admin_site) for inline in inlines]

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
site.register(TeamResult, TeamResultAdmin)
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
site.register(Blindtest, BlindtestAdmin)
site.register(BlindtestRound, BlindtestRoundAdmin)
site.register(BlindtestGuess, BlindtestGuessAdmin)
site.register(Petanque, DisciplineAdmin)
site.register(GeographyQuizz, DisciplineAdmin)
site.register(Basketball, DisciplineAdmin)
site.register(Relay, DisciplineAdmin)
