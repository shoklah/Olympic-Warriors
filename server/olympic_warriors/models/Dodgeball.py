from django.db import models
from django.core.exceptions import ValidationError

from .Discipline import Discipline, Game, GameEvent
from .Team import Team, TeamResult


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
        teams = Team.objects.filter(edition=self.edition, is_active=True)
        for team in teams:
            TeamResult.objects.create(
                team=team, discipline=self, result_type=TeamResult.TeamResultTypes.POINTS, points=0
            )
        self.schedule_games()


class DodgeballEvent(GameEvent):
    """
    Events for Dodgeball games
    """

    class DodgeballEventTypes(models.TextChoices):
        """
        Enum for Dodgeball Game Events Types
        """

        START = 'STA', 'Start'
        END = 'END', 'End'
        HIT = 'HIT', 'Hit'
        CATCH = 'CAT', 'Catch'
        FOUL = 'FOL', 'Foul'
        OUT = 'OUT', 'Out'
        NEW_ROUND = 'NEW', 'New Round'

    event_type = models.CharField(max_length=3, choices=DodgeballEventTypes.choices)

    def is_hit_end_of_round(self) -> bool:
        """
        Check previous events to end the round and grant points
        """
        live_players = 3
        previous_events = DodgeballEvent.objects.filter(game=self.game).order_by('-time')
        for event in previous_events:
            if event.id == self.id:
                continue

            match event.event_type:
                case self.DodgeballEventTypes.HIT:
                    if self.player2.team.id == event.player2.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.CATCH:
                    if live_players < 3 and self.player1.team.id == event.player2.team.id:
                        live_players += 1
                case self.DodgeballEventTypes.FOUL:
                    if self.player2.team.id == event.player1.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.NEW_ROUND | self.DodgeballEventTypes.START:
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
        previous_events = DodgeballEvent.objects.filter(game=self.game).order_by('-time')
        for event in previous_events:
            if event.id == self.id:
                continue

            match event.event_type:
                case self.DodgeballEventTypes.HIT:
                    if self.player1.team.id == event.player2.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.CATCH:
                    if live_players < 3 and self.player1.team.id == event.player1.team.id:
                        live_players += 1
                case self.DodgeballEventTypes.FOUL:
                    if self.player1.team.id == event.player1.team.id:
                        live_players -= 1
                case self.DodgeballEventTypes.NEW_ROUND | self.DodgeballEventTypes.START:
                    return False
                case _:
                    continue
            if live_players == 0:
                return True

        return False

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
        Check if the game is a dodgeball game
        """
        if self.game.discipline.name != 'Dodgeball':
            raise ValidationError('This game is not a dodgeball game')

    def save(self, *args, **kwargs):
        """
        Override the save method to update score and raise alerts if needed.
        """
        self._players_validation()
        self._discipline_validation()
        # Call the original save method to save the object
        super().save(*args, **kwargs)

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
