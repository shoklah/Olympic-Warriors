"""
Admin dashboard configuration for the Olympic Warriors app.
"""

import math

from django.contrib.admin import site, ModelAdmin, TabularInline
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from django.forms import ModelChoiceField, ModelForm
from django.http import HttpRequest
from .badges import refresh
from .throttling import LoginRateThrottle
from .models import (
    MANUAL_CODES,
    Badge,
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
    Fair,
    ObstacleCourse,
    GeneralCultureQuizz,
    Darts,
    Volleyball,
    JumpingRope,
    Dance,
    Frisbee,
    Geoguessr,
    Football,
    Handball,
    BurgerQuizz,
    BlindfoldedObstacleCourse,
    DiscThrow,
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


class ThrottledAdminAuthenticationForm(AdminAuthenticationForm):
    """
    The admin login form, limited per client IP in the same bucket as /auth/token/
    (LoginRateThrottle, LOGIN_THROTTLE_RATE): organisers log into both with one password, so
    either door counts against the other. Every submitted form counts, failed or not; past the
    limit the form comes back with the "throttled" error before any password is checked, so
    the right one is refused too.
    """

    error_messages = {
        **AdminAuthenticationForm.error_messages,
        # In French, like the rest of the admin (LANGUAGE_CODE "fr", no LocaleMiddleware).
        "throttled": "Trop de tentatives de connexion depuis cette adresse. "
        "Réessayez dans %(wait)d s.",
    }

    def clean(self):
        throttle = LoginRateThrottle()
        if not throttle.allow_request(self.request, None):
            # wait() is None when the count outgrew the rate (lowered since): a whole window.
            wait = throttle.wait() or throttle.duration
            raise ValidationError(
                self.error_messages["throttled"],
                code="throttled",
                params={"wait": math.ceil(wait)},
            )
        return super().clean()


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


class PlayerInlineForm(ModelForm):
    """
    On the team page `team` is the inline's hidden foreign key, and the tabular inline
    never renders a hidden field's errors: repeat them among the row's errors, since
    Player.clean() puts its errors on `team`.
    """

    def non_field_errors(self):
        return self.error_class(
            [*super().non_field_errors(), *self.errors.get("team", [])], error_class="nonfield"
        )


class PlayerInline(TabularInline):
    """
    Inline for the Player model to be accessed from the Team model.
    """

    model = Player
    form = PlayerInlineForm
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


class TeamWithYearChoiceField(ModelChoiceField):
    """Team choices labelled with their year: team names repeat across editions."""

    def label_from_instance(self, obj):
        return f"{obj.name} ({obj.edition.year})"


class PlayerAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the Player model.
    """

    list_display = ["user", "rating", "team", "edition"]
    list_editable = ["team"]
    list_filter = ["team", "edition", "is_active"]
    list_select_related = ["user", "edition", "team"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__username",
        "team__name",
        "edition__year",
    ]
    inlines = [PlayerRatingInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Teams labelled `name (year)`, newest edition first."""
        if db_field.name == "team":
            kwargs["queryset"] = Team.objects.select_related("edition").order_by(
                "-edition__year", "name"
            )
            kwargs["form_class"] = TeamWithYearChoiceField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
    search_fields = [
        "player__user__first_name",
        "player__user__last_name",
        "name",
        "identifier",
    ]

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

    list_display = ["name", "edition", "final_rank", "total_points", "ranking"]
    list_editable = ["final_rank"]
    ordering = ["edition", "final_rank", "name"]
    list_filter = ["edition", "is_active"]
    search_fields = ["name", "edition__year"]
    inlines = [PlayerInline]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


def refresh_badges(modeladmin, request, queryset):  # pylint: disable=unused-argument
    """Rebuild every computed badge: streaks and tables span editions, so the selection
    does not matter."""
    report = refresh()
    modeladmin.message_user(
        request,
        f"Badges recalculés : {report.added} ajoutés, {report.removed} retirés, "
        f"{report.kept} inchangés.",
    )


refresh_badges.short_description = "Recalculer les badges (toutes les éditions)"


class EditionAdmin(ModelAdmin):
    """
    Admin dashboard configuration for the Edition model.
    """

    list_display = ["year"]
    list_filter = ["is_active"]
    search_fields = ["year"]
    actions = [refresh_badges]

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
    search_fields = ["name", "edition__year"]

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
    search_fields = ["team__name", "artist", "song"]

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
    search_fields = ["blindtest__name", "order"]

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
    search_fields = ["team__name", "discipline__name"]

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
    search_fields = ["discipline__name", "order"]

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
        "is_played",
        "referees",
        "round",
        "edition",
    ]
    list_editable = ["score1", "score2", "is_played"]
    list_filter = ["discipline", "team1", "team2", "edition", "is_played", "is_active"]
    search_fields = ["discipline__name", "team1__name", "team2__name", "edition__year"]

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
    search_fields = [
        "game__team1__name",
        "game__team2__name",
        "player1__user__first_name",
        "player1__user__last_name",
        "player2__user__first_name",
        "player2__user__last_name",
    ]

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
    search_fields = [
        "game__team1__name",
        "game__team2__name",
        "player1__user__first_name",
        "player1__user__last_name",
        "player2__user__first_name",
        "player2__user__last_name",
        "event_type",
    ]

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
    search_fields = [
        "game__team1__name",
        "game__team2__name",
        "player1__user__first_name",
        "player1__user__last_name",
        "player2__user__first_name",
        "player2__user__last_name",
        "event_type",
    ]

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class BadgeAdminForm(ModelForm):
    """A badge given by hand: only the manual codes. A computed row only edits is_active."""

    class Meta:
        model = Badge
        fields = ["user", "code", "edition", "note", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "code" in self.fields:
            self.fields["code"].choices = [
                (value, label) for value, label in Badge.Codes.choices if value in MANUAL_CODES
            ]


class BadgeAdmin(ModelAdmin):
    """
    Badges: computed ones (badges.refresh()) are read-only but is_active, which revokes
    them; the ones given by hand are editable, and adding one gives it by hand.
    """

    form = BadgeAdminForm
    list_display = [
        "user", "code", "edition", "tier", "discipline", "partner", "is_manual", "is_active"
    ]
    list_filter = ["code", "edition", "is_manual", "is_active"]
    search_fields = ["user__first_name", "user__last_name"]
    list_select_related = ["user", "edition", "partner"]

    COMPUTED_FIELDS = ("user", "code", "edition", "tier", "discipline", "partner", "is_active")
    MANUAL_FIELDS = ("user", "code", "edition", "note", "is_active")

    def get_fields(self, request, obj=None):
        if obj is not None and not obj.is_manual:
            return self.COMPUTED_FIELDS
        return self.MANUAL_FIELDS

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and not obj.is_manual:
            return self.COMPUTED_FIELDS[:-1]
        return ()

    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_manual = True
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        """
        Filter the request to only show active items.
        """
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


site.login_form = ThrottledAdminAuthenticationForm

site.register(Player, PlayerAdmin)
site.register(Team, TeamAdmin)
site.register(Edition, EditionAdmin)
site.register(Badge, BadgeAdmin)
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
site.register(Fair, DisciplineAdmin)
site.register(ObstacleCourse, DisciplineAdmin)
site.register(GeneralCultureQuizz, DisciplineAdmin)
site.register(Darts, DisciplineAdmin)
site.register(Volleyball, DisciplineAdmin)
site.register(JumpingRope, DisciplineAdmin)
site.register(Dance, DisciplineAdmin)
site.register(Frisbee, DisciplineAdmin)
site.register(Geoguessr, DisciplineAdmin)
site.register(Football, DisciplineAdmin)
site.register(Handball, DisciplineAdmin)
site.register(BurgerQuizz, DisciplineAdmin)
site.register(BlindfoldedObstacleCourse, DisciplineAdmin)
site.register(DiscThrow, DisciplineAdmin)
