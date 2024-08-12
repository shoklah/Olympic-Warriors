from django.db import models

from .Discipline import Discipline, Game, GameEvent


class Rugby(Discipline):
    """
    Rugby is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to rugby and schedule games.
        """
        self.name = 'Rugby'
        super().save(*args, **kwargs)
        self.schedule_games()


class RugbyEvent(GameEvent):
    """
    Events for Rugby games
    """

    class RugbyEventTypes(models.TextChoices):
        """
        Enum for Rugby Game Events Types
        """

        TRY = 'TRY', 'Try'
        TACKLE = 'TKL', 'Tackle'
        FOUL = 'FOL', 'Foul'
        OUTBOUNDS = 'OUT', 'Outbounds'

    event_type = models.CharField(max_length=3, choices=RugbyEventTypes.choices)

    def process_try_points(self) -> int:
        """
        Check previous events to grant the right number of points for a try according to tackles
        """
        points = 3
        previous_events = RugbyEvent.objects.filter(game=self.game).order_by('-time').values()
        for event in previous_events:
            match event.event_type:
                case self.RugbyEventTypes.TRY | self.RugbyEventTypes.OUTBOUNDS:
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

    def save(self, *args, **kwargs):
        """
        Override the save method to update score and raise alerts if needed.
        """
        match self.event_type:
            case self.RugbyEventTypes.TRY:
                points = self.process_try_points()
                game = Game.objects.get(id=self.game.id)
                if game.team1.id == self.player1.team.id:
                    game.score1 += points
                else:
                    game.score2 += points
                game.save()
        # Call the original save method to save the object
        super().save(*args, **kwargs)
