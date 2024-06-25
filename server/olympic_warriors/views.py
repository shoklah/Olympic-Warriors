from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializer import PlayerSerializer
from .models import Player

import logging

logger = logging.getLogger(__name__)


@require_GET
@login_required
def home(request):
    return render(request, "olympic_warriors/home.html")


@require_GET
@login_required
def profile(request):
    return render(request, "olympic_warriors/profile.html")


@api_view(["GET"])
def getPlayers(request):
    players = Player.objects.all()
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)
