from django.core.management.base import BaseCommand, CommandError
from tournament.models import Tournament, Match
from tournament.services import TournamentService, VotingService


class Command(BaseCommand):
    help = 'Advance tournament to next round by finalizing current matches'

    def add_arguments(self, parser):
        parser.add_argument(
            'tournament_id',
            type=str,
            help='Tournament UUID to advance'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force advance even if matches have no votes (random winner)',
        )

    def handle(self, *args, **options):
        tournament_id = options['tournament_id']
        force = options['force']
        
        try:
            tournament = Tournament.objects.get(id=tournament_id)
        except Tournament.DoesNotExist:
            raise CommandError(f'Tournament "{tournament_id}" does not exist.')
        
        if tournament.status != 'ONGOING':
            raise CommandError(f'Tournament "{tournament.name}" is not ongoing.')
        
        # Get current round matches
        current_matches = Match.objects.filter(
            tournament=tournament,
            round_number=tournament.current_round,
            status='VOTING'
        )
        
        if not current_matches.exists():
            self.stdout.write(
                self.style.WARNING('No voting matches found in current round.')
            )
        
        # Finalize matches
        finalized_count = 0
        for match in current_matches:
            if match.total_votes == 0 and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f'Match {match} has no votes. Use --force to advance anyway.'
                    )
                )
                continue
            
            if VotingService.finalize_match(match):
                finalized_count += 1
                self.stdout.write(
                    f'Finalized match: {match.song1} vs {match.song2} -> {match.winner}'
                )
        
        self.stdout.write(f'Finalized {finalized_count} matches.')
        
        # Advance tournament
        advanced = TournamentService.advance_tournament(tournament)
        
        if advanced:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Tournament "{tournament.name}" advanced to round {tournament.current_round}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Tournament "{tournament.name}" completed!'
                )
            )