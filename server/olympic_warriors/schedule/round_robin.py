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

    @param game_without_referees: list of games without referees for this batch of games
    @param leftover_team_ids: set of team ids that can be referees for this batch of games
    """
    Game = _get_game_model()

    for game in game_without_referees:
        if not leftover_team_ids:
            # Nobody left to referee (e.g. only two teams): keep the default referee.
            return

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
                last_round_best_referee = None

            # If the team has refereed the same number of games,
            # pick the one that didn't referee for longer
            elif referee_score == best_referee_score:
                if last_round_best_referee is None:
                    last_round_best_referee = _get_last_round_as_referee(
                        discipline_id,
                        best_referee_id
                    )

                if _get_last_round_as_referee(discipline_id, team_id) < last_round_best_referee:
                    best_referee_id = team_id
                    best_referee_score = referee_score
                    last_round_best_referee = None

        game.referees = Team.objects.get(id=best_referee_id)
        game.save()
        leftover_team_ids.remove(best_referee_id)


def round_robin_pairings(teams: list[Team]) -> list[list[tuple[Team, Team]]]:
    """
    Build the pairings of a full round-robin with the circle method: every team meets every
    other team exactly once, and every team plays in every round. With an odd number of teams,
    one team sits out each round.

    @param teams: teams to pair

    @return: list of rounds, each round being the list of (team1, team2) pairings played in it
    """
    rotation = list(teams)
    if len(rotation) % 2:
        rotation.append(None)  # bye

    half = len(rotation) // 2
    rounds = []
    for _ in range(len(rotation) - 1):
        pairings = [
            (rotation[i], rotation[-1 - i])
            for i in range(half)
            if rotation[i] is not None and rotation[-1 - i] is not None
        ]
        rounds.append(pairings)
        # Keep the first team in place and rotate every other team by one position
        rotation = [rotation[0], rotation[-1]] + rotation[1:-1]

    return rounds


def schedule_round_robin_games(discipline_id: int) -> None:
    """
    Schedule round-robin games for the discipline, including teams refereeing.
    Applicable to team sports.

    A round holds every pairing of a round-robin round, so every team plays once per round.
    Games are split in batches of simultaneous games, refereed by the teams not playing in the
    batch. When max_rounds is not set, it defaults to the number of rounds needed for every
    team to meet every other team once. When it is larger, pairings start over.
    """
    Discipline = _get_discipline_model()
    Game = _get_game_model()
    TeamSportRound = _get_team_sport_round_model()

    discipline = Discipline.objects.get(id=discipline_id)
    teams = list(Team.objects.filter(edition=discipline.edition, is_active=True).order_by("id"))

    if len(teams) < 2:
        raise ValueError("Not enough teams to schedule round-robin games.")

    # A game keeps three teams busy: two playing and one refereeing
    simultaneous_games = max(1, len(teams) // 3)
    pairing_rounds = round_robin_pairings(teams)

    if not discipline.max_rounds:
        discipline.max_rounds = len(pairing_rounds)
        discipline.save(update_fields=["max_rounds"])

    team_ids = {team.id for team in teams}

    for round_index in range(discipline.max_rounds):
        game_round = TeamSportRound.objects.create(discipline=discipline, order=round_index)
        pairings = pairing_rounds[round_index % len(pairing_rounds)]

        for batch_start in range(0, len(pairings), simultaneous_games):
            batch = pairings[batch_start:batch_start + simultaneous_games]
            leftover_team_ids = set(team_ids)
            games_without_referees = []

            for team1, team2 in batch:
                games_without_referees.append(
                    Game.objects.create(
                        discipline=discipline,
                        round=game_round,
                        team1=team1,
                        team2=team2,
                        referees=team1,
                        edition=discipline.edition,
                    )
                )
                leftover_team_ids.discard(team1.id)
                leftover_team_ids.discard(team2.id)

            _assign_referees(discipline_id, games_without_referees, leftover_team_ids)
