
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

def schedule_swiss_games(discipline_id: int):
    """
    Schedule Swiss games for a discipline.
    """
    Game = _get_game_model()
    TeamSportRound = _get_team_sport_round_model()
    discipline = _get_discipline_model().objects.get(pk=discipline_id)
    last_round = discipline.rounds.filter(
        is_active=True).order_by('-order').first()
    round_index = (last_round.order if last_round else -1) + 1


    if round_index > discipline.max_rounds:
        return

    team_ids = TeamResult.objects.filter(discipline=discipline, is_active=True).order_by('points', 'time').values_list('team_id', flat=True)
    round = TeamSportRound.objects.create(discipline=discipline, order=round_index)

    for i in range(0, len(team_ids), 2):
        if i + 1 < len(team_ids):
            team1 = Team.objects.get(pk=team_ids[i])
            team2 = Team.objects.get(pk=team_ids[i + 1])
            game = Game(
                discipline=discipline,
                round=round,
                team1=team1,
                team2=team2,
                referees=team1,  # No referee for Swiss rounds for now
                edition=discipline.edition
            )
            game.save()