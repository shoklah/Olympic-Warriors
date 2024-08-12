from django.db import models

from .Discipline import Discipline, Game, GameEvent


class Dodgeball(Discipline):
    """
    Dodgeball is a discipline that takes place in an edition of the Olympic Warriors.
    """

    def save(self, *args, **kwargs):
        """
        Override save method to set discipline name to dodgeball
        """
        self.name = 'Dodgeball'
        super().save(*args, **kwargs)
        self.schedule_games()


class DodgeballEvent(GameEvent):
    """
    Events for Dodgeball games
    """

    class DodgeballEventTypes(models.TextChoices):
        """
        Enum for Dodgeball Game Events Types
        """

        HIT = 'HIT', 'Hit'
        FOUL = 'FOL', 'Foul'
        OUTBOUNDS = 'OUT', 'Outbounds'
        NEW_ROUND = 'NEW', 'New Round'

    event_type = models.CharField(max_length=3, choices=DodgeballEventTypes.choices)

    def is_hit_end_of_round(self) -> bool:
        """
        Check previous events to end the round and grant points
        """
        live_players = 3
        previous_events = DodgeballEvent.objects.filter(game=self.game).order_by('-time').values()
        for event in previous_events:
            match event.event_type:
                case self.DodgeballEventTypes.HIT:
                    if self.player2.team.id == event.player2.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.FOUL:
                    if self.player2.team.id == event.player1.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.NEW:
                    return False
                case _:
                    continue
            if live_players == 0:
                return True

        return False

    def is_foul_end_of_round(self) -> bool:
        """
        Check previous events to end the round and grant points
        """
        live_players = 3
        previous_events = DodgeballEvent.objects.filter(game=self.game).order_by('-time').values()
        for event in previous_events:
            match event.event_type:
                case self.DodgeballEventTypes.HIT:
                    if self.player1.team.id == event.player2.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.FOUL:
                    if self.player1.team.id == event.player1.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.NEW:
                    return False
                case _:
                    continue
            if live_players == 0:
                return True

        return False

    def save(self, *args, **kwargs):
        """
        Override the save method to update score and raise alerts if needed.
        """
        match self.event_type:
            case self.DodgeballEventTypes.HIT:
                if self.is_hit_end_of_round():
                    game = Game.objects.get(id=self.game.id)
                    if game.team1.id == self.player1.team.id:
                        game.score1 += 1
                    else:
                        game.score2 += 1
                    game.save()
            case self.DodgeballEventTypes.FOUL:
                if self.is_foul_end_of_round():
                    game = Game.objects.get(id=self.game.id)
                    if game.team1.id == self.player1.team.id:
                        game.score2 += 1
                    else:
                        game.score1 += 1
                    game.save()
        # Call the original save method to save the object
        super().save(*args, **kwargs)
