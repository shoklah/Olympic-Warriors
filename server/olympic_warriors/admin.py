from django.contrib.admin import site, ModelAdmin, TabularInline
from django.http import HttpRequest
from .models import Player, Team, Edition, Registration, PlayerRating


def request_only_active(request: HttpRequest) -> HttpRequest:
    if not request.GET.get("is_active__exact"):
        q = request.GET.copy()
        q["is_active__exact"] = "1"
        request.GET = q
        request.META["QUERY_STRING"] = request.GET.urlencode()
    return request


class PlayerRatingInline(TabularInline):
    model = PlayerRating
    extra = 1


class PlayerInline(TabularInline):
    model = Player
    extra = 1


class PlayerAdmin(ModelAdmin):
    list_display = ["user", "rating", "team", "edition"]
    list_filter = ["team", "edition", "is_active"]
    search_fields = ["name", "team", "user", "edition"]
    inlines = [PlayerRatingInline]

    def changelist_view(self, request, extra_context=None):
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class PlayerRatingAdmin(ModelAdmin):
    list_display = ["player", "name", "identifier", "rating"]
    list_filter = ["player__user", "name", "identifier", "player__edition", "is_active"]
    search_fields = ["player", "name", "identifier"]

    def changelist_view(self, request, extra_context=None):
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class TeamAdmin(ModelAdmin):
    list_display = ["name", "edition"]
    list_filter = ["edition", "is_active"]
    search_fields = ["name", "edition"]
    inlines = [PlayerInline]

    def changelist_view(self, request, extra_context=None):
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class EditionAdmin(ModelAdmin):
    list_display = ["year"]
    list_filter = ["is_active"]
    search_fields = ["year"]

    def changelist_view(self, request, extra_context=None):
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


site.register(Player, PlayerAdmin)
site.register(Team, TeamAdmin)
site.register(Edition, EditionAdmin)
site.register(Registration)
site.register(PlayerRating, PlayerRatingAdmin)
