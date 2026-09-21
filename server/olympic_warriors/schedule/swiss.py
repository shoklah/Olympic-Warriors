from math import ceil, log2

from django.apps import apps
from olympic_warriors.models.Team import Team, TeamResult


def _get_discipline_model():
    """
    Get the Discipline model from the apps registry.
    """
    return apps.get_model('olympic_warriors', 'Discipline')


def _get_game_model():
    """
    Get the Game model from the apps registry.
    """
    return apps.get_model('olympic_warriors', 'Game')


def _get_team_sport_round_model():
    """
    Get the TeamSportRound model from the apps registry.
    """
    return apps.get_model('olympic_warriors', 'TeamSportRound')


def default_swiss_rounds(team_count: int) -> int:
    """
    Number of Swiss rounds needed to single out a winner: log2 of the number of teams, rounded up.

    @param team_count: number of teams taking part

    @return: number of rounds, at least 1
    """
    return max(1, ceil(log2(team_count))) if team_count > 1 else 1


def schedule_swiss_games(discipline_id: int):
    """
    Schedule the next Swiss round for a discipline, pairing teams by their current results.
    Does nothing once max_rounds rounds have been scheduled. When max_rounds is not set,
    it defaults to log2 of the number of teams, rounded up.
    """
    Game = _get_game_model()
    TeamSportRound = _get_team_sport_round_model()
    discipline = _get_discipline_model().objects.get(pk=discipline_id)

    team_results = TeamResult.objects.filter(discipline=discipline, is_active=True)
    if team_results.count() < 2:
        raise ValueError("Not enough teams to schedule Swiss games.")

    if not discipline.max_rounds:
        discipline.max_rounds = default_swiss_rounds(team_results.count())
        discipline.save(update_fields=["max_rounds"])

    last_round = discipline.rounds.filter(is_active=True).order_by('-order').first()
    round_index = (last_round.order if last_round else -1) + 1

    if round_index >= discipline.max_rounds:
        return

    team_ids = list(team_results.order_by('points', 'time').values_list('team_id', flat=True))
    game_round = TeamSportRound.objects.create(discipline=discipline, order=round_index)

    for i in range(0, len(team_ids) - 1, 2):
        team1 = Team.objects.get(pk=team_ids[i])
        team2 = Team.objects.get(pk=team_ids[i + 1])
        Game.objects.create(
            discipline=discipline,
            round=game_round,
            team1=team1,
            team2=team2,
            referees=team1,  # No referee for Swiss rounds for now
            edition=discipline.edition,
        )
