from copy import deepcopy

from django.apps import apps
from olympic_warriors.models.Team import Team


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


def _get_last_round_as_referee(discipline_id: int, team_id: int) -> int:
    """
    Get the last round order in which a team was a referee.

    @param team_id: id of the team to search for

    @return: order of the last round in which the team was a referee, -1 if never
    """
    Game = _get_game_model()

    last_game_refereed = (
        Game.objects.filter(referees__id=team_id, is_active=True)
        .filter(discipline__id=discipline_id)
        .order_by("-round__order")
        .first()
    )

    if not last_game_refereed:
        return -1
    return last_game_refereed.round.order



def _assign_referees(
    discipline_id: int, game_without_referees: list, leftover_team_ids: set[int]
) -> None:
    """
    Assign referees to games without referees while ensuring best possible distribution.

    @param game_without_referees: list of games without referees for this round iteration
    @param leftover_team_ids: set of team ids that can be referees for this round iteration
    """
    Game = _get_game_model()

    for game in game_without_referees:
        best_referee_id: int = None
        best_referee_score: int = None
        last_round_best_referee: int = None
        for team_id in leftover_team_ids:
            referee_score = Game.objects.filter(
                referees__id=team_id, discipline__id=discipline_id, is_active=True
            ).count()

            # Assign the first team as the best referee, or the one with the refereed games
            if not best_referee_id or referee_score < best_referee_score:
                best_referee_id = team_id
                best_referee_score = referee_score

            # If the team has refereed the same number of games,
            # pick the one that didn't referee for longer
            elif referee_score == best_referee_score:
                if not last_round_best_referee:
                    last_round_best_referee = _get_last_round_as_referee(
                        discipline_id,
                        best_referee_id
                    )

                if _get_last_round_as_referee(discipline_id, team_id) < last_round_best_referee:
                    best_referee_id = team_id
                    best_referee_score = referee_score

        game.referees = Team.objects.get(id=best_referee_id)
        game.save()
        leftover_team_ids.remove(best_referee_id)


def _create_round_iterations(
    discipline_id: int,
    l1: list[Team],
    l2: list[Team],
    leftover_team_ids: set[int],
    game_round_id: int,
    game_index: int,
    iteration_index: int,
    simultaneous_games: int,
    ) -> int:
    """
    Create round iterations for team sports.

    @param l1: list of teams in the first half of the round
    @param l2: list of teams in the second half of the round
    @param leftover_team_ids: set of team ids that can be referees for this round iteration
    @param game_round: round of the game
    @param game_index: index of the game in the round
    @param iteration_index: index of the iteration in the round
    @param simultaneous_games: number of simultaneous games in the round

    @return: game index
    """
    games_without_referees = []
    Discipline = _get_discipline_model()
    Game = _get_game_model()
    discipline = Discipline.objects.get(id=discipline_id)

    # Create games for this iteration, hence the number of simultaneous games for a round
    while game_index < simultaneous_games * (iteration_index + 1):
        games_without_referees.append(
            Game.objects.create(
                discipline=discipline,
                round_id=game_round_id,
                team1=l1[game_index],
                team2=l2[game_index],
                referees=l1[game_index],
                edition=discipline.edition,
            )
        )
        leftover_team_ids.remove(l1[game_index].id)
        leftover_team_ids.remove(l2[game_index].id)
        game_index += 1

    _assign_referees(discipline_id, games_without_referees, leftover_team_ids)

    return game_index


def schedule_round_robin_games(discipline_id: int) -> None:
    """
    Schedule round-robin games for the discipline, including teams refereeing.
    Applicable to team sports.
    """
    Discipline = _get_discipline_model()
    TeamSportRound = _get_team_sport_round_model()

    discipline = Discipline.objects.get(id=discipline_id)
    teams = Team.objects.filter(edition=discipline.edition, is_active=True)

    if len(teams) < 2:
        raise ValueError("Not enough teams to schedule round-robin games.")

    simultaneous_games = len(teams) // 3
    iteration_per_round = (len(teams) // 2) // simultaneous_games

    if not discipline.max_rounds:
        discipline.max_rounds = len(teams) - 1
        discipline.save()

    team_ids = {team.id for team in teams}

    # Split teams in two halves for round-robin
    l1 = teams[: len(teams) // 2]
    l2 = teams[len(teams) // 2:]
    l2.reverse()

    for round_index in range(discipline.max_rounds):
        game_round = TeamSportRound.objects.create(discipline=discipline, order=round_index)
        game_index = 0

        for iteration_index in range(iteration_per_round):
            game_index = _create_round_iterations(
                discipline_id,
                l1,
                l2,
                deepcopy(team_ids),
                game_round.id,
                game_index,
                iteration_index,
                simultaneous_games,
            )

        # Rotate teams for next round
        l2.append(l1.pop())
        l1.insert(1, l2.pop(0))
