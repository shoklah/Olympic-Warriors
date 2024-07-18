from django.contrib.admin import site, ModelAdmin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.http import HttpRequest
from .models import Player, Team, Edition, Registration, PlayerRating


def request_only_active(request: HttpRequest) -> HttpRequest:
    if not request.GET.get("is_active__exact"):
        q = request.GET.copy()
        q["is_active__exact"] = "1"
        request.GET = q
        request.META["QUERY_STRING"] = request.GET.urlencode()
    return request


class PlayerAdmin(ModelAdmin):
    list_display = ["user", "rating", "team"]
    search_fields = ["name", "team", "user"]

    def changelist_view(self, request, extra_context=None):
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class PlayerRatingAdmin(ModelAdmin):
    list_display = ["player", "name", "identifier", "rating"]
    search_fields = ["player", "name", "identifier"]

    def changelist_view(self, request, extra_context=None):
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


class TeamAdmin(ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]

    def changelist_view(self, request, extra_context=None):
        request = request_only_active(request)
        return super().changelist_view(request, extra_context)


site.register(Player, PlayerAdmin)
site.register(Team, TeamAdmin)
site.register(Edition)
site.register(Registration)
site.register(PlayerRating, PlayerRatingAdmin)
