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

from django.contrib import admin
from django.urls import path, include
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
    # players
    path("players/<int:player_id>/", views.getPlayer),
    path("players/", views.getPlayers),
    path("players/edition/<int:edition_id>/", views.getPlayersByEdition),
    path("players/team/<int:team_id>/", views.getPlayersByTeam),
    # editions
    path("editions/<int:edition_id>/", views.getEdition),
    path("editions/", views.getEditions),
    # teams
    path("teams/<int:team_id>/", views.getTeam),
    path("teams/", views.getTeams),
    # disciplines
    path("disciplines/<int:discipline_id>/", views.getDiscipline),
    path("disciplines/", views.getDisciplines),
    path("disciplines/<int:edition_id>/", views.getDisciplinesByEdition),
    # player ratings
    path("ratings/<int:rating_id>/", views.getPlayerRating),
    path("ratings/", views.getPlayerRatings),
    path("ratings/player/<int:player_id>/", views.getPlayerRatingsByPlayer),
]

env = os.environ.get("ENV", "dev").lower()

if env == "dev":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
