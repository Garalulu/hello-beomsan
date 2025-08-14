from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from tournament.models import Tournament, Song
from tournament.services import TournamentService


class Command(BaseCommand):
    help = 'Create a new tournament with 128 randomly selected songs'

    def add_arguments(self, parser):
        parser.add_argument(
            'name',
            type=str,
            help='Tournament name'
        )
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='Tournament description'
        )
        parser.add_argument(
            '--creator',
            type=str,
            help='Username of tournament creator (uses first superuser if not specified)'
        )

    def handle(self, *args, **options):
        name = options['name']
        description = options['description']
        creator_username = options['creator']
        
        # Get creator user
        if creator_username:
            try:
                creator = User.objects.get(username=creator_username)
            except User.DoesNotExist:
                raise CommandError(f'User "{creator_username}" does not exist.')
        else:
            creator = User.objects.filter(is_superuser=True).first()
            if not creator:
                raise CommandError('No superuser found. Please create one first.')
        
        # Check if enough songs exist
        song_count = Song.objects.count()
        if song_count < 128:
            raise CommandError(f'Need at least 128 songs, but only {song_count} found.')
        
        self.stdout.write(f'Creating tournament "{name}" with {song_count} available songs...')
        
        try:
            # Create tournament
            tournament = Tournament.objects.create(
                name=name,
                description=description,
                created_by=creator
            )
            
            # Create bracket
            TournamentService.create_tournament_bracket(tournament)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created tournament "{name}" (ID: {tournament.id})'
                )
            )
            self.stdout.write(f'Tournament has {tournament.songs.count()} songs')
            self.stdout.write(f'First round has {tournament.matches.filter(round_number=1).count()} matches')
            
        except Exception as e:
            raise CommandError(f'Error creating tournament: {str(e)}')