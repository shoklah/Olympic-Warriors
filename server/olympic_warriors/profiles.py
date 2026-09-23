"""
Player records across editions, from the team standings of each edition: a person's rank
in an edition is their team's rank, and nothing is stored.

The rules (see the player profiles design spec under docs/superpowers/specs/):
- a person is a user with an active Player in an active edition; one participation per
  (user, edition): the lowest id among the rows with a valid team (active, of the
  player's edition), else the lowest id;
- an edition is finished once its end_date is before today in Europe/Paris; an
  unfinished edition gives no rank, so its standings are not computed;
- a participation counts when finished, ranked, and the edition has at least 2 teams;
- the share beaten is (teams - rank) / (teams - 1), clamped to [0, 1];
- averages are over counted participations: mean rank to one decimal, mean share as a
  whole percentage;
- the leaderboard sorts ranked people by share, then mean rank, then counted editions,
  then name; equal (share, mean rank) pairs share a position; people with nothing
  counted follow by name, without a position.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db.models import Count, Q

from .models import Edition, Player
from .standings import compute_standings

PARIS = ZoneInfo("Europe/Paris")


def paris_today():
    """Today's calendar date where the event takes place; the server clock runs in UTC."""
    return datetime.now(PARIS).date()


def beaten_share(rank, teams):
    """Share of the other teams finished behind: 1.0 for first, 0.0 for last."""
    if rank is None or teams < 2:
        return None
    return min(1.0, max(0.0, (teams - rank) / (teams - 1)))


@dataclass(frozen=True)
class Participation:
    """One person's edition: their team, its rank among `teams` active teams, and whether
    the edition is over. rank is None without a team, before the end, or in a
    hand-ranked edition where the team has no final_rank."""

    year: int
    team_id: int | None
    team_name: str | None
    rank: int | None
    teams: int
    finished: bool

    @property
    def counted(self):
        """Whether the edition feeds the averages: over, ranked, and more than one team."""
        return self.finished and self.rank is not None and self.teams >= 2


def _valid_team(player):
    """The player's team when it is active and belongs to the player's edition."""
    team = player.team
    if team is None or not team.is_active or team.edition_id != player.edition_id:
        return None
    return team


def participations(today=None):
    """
    Every person's participations, newest edition first, keyed by user id:
    {user_id: (user, (Participation, ...))}.
    Queries: the editions, the players, then three per finished edition with a player.
    """
    today = today or paris_today()
    editions = {
        edition.id: edition
        for edition in Edition.objects.filter(is_active=True).annotate(
            team_count=Count("team", filter=Q(team__is_active=True))
        )
    }
    players = (
        Player.objects.filter(is_active=True, edition__is_active=True)
        .select_related("user", "team")
        .order_by("id")
    )

    chosen = {}  # (user id, edition id) -> the Player row that stands for it
    for player in players:
        key = (player.user_id, player.edition_id)
        kept = chosen.get(key)
        if kept is None or (_valid_team(kept) is None and _valid_team(player) is not None):
            chosen[key] = player

    finished = {pk for pk, edition in editions.items() if edition.end_date < today}
    played = {edition_id for _, edition_id in chosen}
    standings = {pk: compute_standings(editions[pk]) for pk in sorted(played & finished)}

    users = {}
    by_user = defaultdict(list)
    for (user_id, edition_id), player in chosen.items():
        edition = editions[edition_id]
        team = _valid_team(player)
        rank = None
        if team is not None and edition_id in standings:
            rank = standings[edition_id].team(team.id).ranking
        users[user_id] = player.user
        by_user[user_id].append(
            Participation(
                year=edition.year,
                team_id=team.id if team else None,
                team_name=team.name if team else None,
                rank=rank,
                teams=edition.team_count,
                finished=edition_id in finished,
            )
        )

    return {
        user_id: (users[user_id], tuple(sorted(parts, key=lambda p: p.year, reverse=True)))
        for user_id, parts in by_user.items()
    }
