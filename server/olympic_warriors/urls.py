"""
URL configuration for olympic_warriors project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import os
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from rest_framework.authtoken import views as auth_views
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"
    ),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # admin
    path("admin/", admin.site.urls),
    # authentication
    path("auth/token/", auth_views.obtain_auth_token, name="auth_token"),
    # players
    path("player/<int:player_id>/", views.getPlayer),
    path("players/", views.getPlayers),
    path("players/edition/<int:edition_id>/", views.getPlayersByEdition),
    path("players/team/<int:team_id>/", views.getPlayersByTeam),
    # editions
    path("edition/<int:edition_id>/", views.getEdition),
    path("editions/", views.getEditions),
    # teams
    path("team/<int:team_id>/", views.getTeam),
    path("teams/", views.getTeams),
    # disciplines
    path("discipline/<int:discipline_id>/", views.getDiscipline),
    path("disciplines/", views.getDisciplines),
    path("disciplines/<int:edition_id>/", views.getDisciplinesByEdition),
    # player ratings
    path("rating/<int:rating_id>/", views.getPlayerRating),
    path("ratings/", views.getPlayerRatings),
    path("ratings/player/<int:player_id>/", views.getPlayerRatingsByPlayer),
    # games
    path("game/<int:game_id>/", views.getGame),
    path("games/", views.getGames),
    path("games/discipline/<int:discipline_id>/", views.getGamesByDiscipline),
    path("games/team/<int:team_id>/", views.getGamesByTeam),
    path("games/team/<int:team_id>/played/", views.getPlayedGamesByTeam),
    path("games/team/<int:team_id>/refereed/", views.getRefereedGamesByTeam),
    path("games/edition/<int:edition_id>/", views.getGamesByEdition),
    path(
        "games/discipline/<int:discipline_id>/team/<int:team_id>/",
        views.getGamesByDisciplineAndTeam,
    ),
    path(
        "games/discipline/<int:discipline_id>/team/<int:team_id>/played/",
        views.getPlayedGamesByDisciplineAndTeam,
    ),
    path(
        "games/discipline/<int:discipline_id>/team/<int:team_id>/refereed/",
        views.getRefereedGamesByDisciplineAndTeam,
    ),
    path("games/round/<int:round>/", views.getGamesByRound),
    # rounds
    path("round/<int:round_id>/", views.getRound),
    path("rounds/", views.getRounds),
    path("rounds/discipline/<int:discipline_id>/", views.getRoundsByDiscipline),
    # blindtest guesses
    path("blindtest_guess/<int:guess_id>/", views.getBlindtestGuess),
    path("blindtest_guesses/", views.getBlindtestGuesses),
    path("blindtest_guesses/team/<int:team_id>/", views.getBlindtestGuessesByTeam),
    path("blindtest_guesses/blindtest/<int:blindtest_id>/", views.getBlindtestGuessesByBlindtest),
    path(
        "blindtest_guesses/blindtest/<int:blindtest_id>/team/<int:team_id>/",
        views.getBlindtestGuessesByTeamAndBlindtest,
    ),
    path("blindtest_guesses/artist/correct/", views.getCorrectArtistBlindtestGuesses),
    path("blindtest_guesses/song/correct/", views.getCorrectSongBlindtestGuesses),
    path("blindtest_guesses/artist/correct/song/correct/", views.getCorrectBlindtestGuesses),
    # team results
    path("result/<int:result_id>/", views.getTeamResult),
    path("results/", views.getTeamResults),
    path("results/team/<int:team_id>/", views.getTeamResultsByTeam),
    path("results/discipline/<int:discipline_id>/", views.getTeamResultsByDiscipline),
    path("results/edition/<int:edition_id>/", views.getTeamResultsByEdition),
]

env = os.environ.get("ENV", "dev").lower()

if env == "dev":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
