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

from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def paris_today():
    """Today's calendar date where the event takes place; the server clock runs in UTC."""
    return datetime.now(PARIS).date()


def beaten_share(rank, teams):
    """Share of the other teams finished behind: 1.0 for first, 0.0 for last."""
    if rank is None or teams < 2:
        return None
    return min(1.0, max(0.0, (teams - rank) / (teams - 1)))
