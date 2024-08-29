from django.db import models
from django.core.exceptions import ValidationError

from .Discipline import Discipline, Game, GameEvent
from .Team import Team, TeamResult


class Rugby(Discipline):
    """
    Rugby is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to rugby, schedule games and initialize team results.
        """
        self.name = 'Rugby'
        super().save(*args, **kwargs)
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            TeamResult.objects.create(
                team=team, discipline=self, result_type=TeamResult.TeamResultTypes.POINTS, points=0
            )
        self.schedule_games()


class RugbyEvent(GameEvent):
    """
    Events for Rugby games
    """

    class RugbyEventTypes(models.TextChoices):
        """
        Enum for Rugby Game Events Types
        """

        START = 'STA', 'Start'
        END = 'END', 'End'
        TRY = 'TRY', 'Try'
        STEAL = 'STL', 'Steal'
        TACKLE = 'TKL', 'Tackle'
        FOUL = 'FOL', 'Foul'
        OUT = 'OUT', 'Out'

    event_type = models.CharField(max_length=3, choices=RugbyEventTypes.choices)

    def process_try_points(self) -> int:
        """
        Check previous events to grant the right number of points for a try according to tackles
        """
        points = 3
        previous_events = RugbyEvent.objects.filter(game=self.game).order_by('-time')
        for event in previous_events:
            if event.id == self.id:
                continue

            match event.event_type:
                case (
                    self.RugbyEventTypes.TRY
                    | self.RugbyEventTypes.OUT
                    | self.RugbyEventTypes.START
                    | self.RugbyEventTypes.STEAL
                ):
                    return points
                case self.RugbyEventTypes.TACKLE:
                    if self.player1.team == event.player1.team:
                        return points
                    points -= 1
                case self.RugbyEventTypes.FOUL:
                    if self.player1.team == event.player1.team:
                        return points
                case _:
                    continue

        return points

    def _players_validation(self):
        """
        Check if players are part of the teams playing the game associated with the event
        """
        if self.player1 and self.player1.team not in [self.game.team1, self.game.team2]:
            raise ValidationError('Player 1 is not part of the teams playing the game')
        elif self.player2 and self.player2.team not in [self.game.team1, self.game.team2]:
            raise ValidationError('Player 2 is not part of the teams playing the game')

    def _discipline_validation(self):
        """
        Check if the game discipline is Rugby
        """
        if self.game.discipline.name != 'Rugby':
            raise ValidationError('The discipline of the game is not Rugby')

    def save(self, *args, **kwargs):
        """
        Override the save method to update score and raise alerts if needed.
        """
        self._players_validation()
        self._discipline_validation()
        # Call the original save method to save the object
        super().save(*args, **kwargs)

        match self.event_type:
            case self.RugbyEventTypes.TRY:
                points = self.process_try_points()
                game = Game.objects.get(id=self.game.id)
                if game.team1.id == self.player1.team.id:
                    game.score1 += points
                else:
                    game.score2 += points
                game.save()
