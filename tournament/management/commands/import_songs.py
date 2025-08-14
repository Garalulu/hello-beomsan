import os
import csv
from django.core.management.base import BaseCommand, CommandError
from tournament.models import Song


class Command(BaseCommand):
    help = 'Import songs from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to CSV file with song data'
        )
        parser.add_argument(
            '--audio-dir',
            type=str,
            required=True,
            help='Directory path where audio files are stored (Fly volume path)'
        )
        parser.add_argument(
            '--image-dir',
            type=str,
            help='Directory path where background images are stored (Fly volume path)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        audio_dir = options['audio_dir']
        image_dir = options['image_dir'] or ''
        
        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file "{csv_file}" does not exist.')
        
        self.stdout.write(f'Importing songs from {csv_file}...')
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    title = row.get('title', '').strip()
                    artist = row.get('artist', '').strip()
                    audio_filename = row.get('audio_file', '').strip()
                    image_filename = row.get('background_image', '').strip()
                    
                    if not title or not audio_filename:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Row {row_num}: Missing required fields (title, audio_file)'
                            )
                        )
                        error_count += 1
                        continue
                    
                    # Construct file paths
                    audio_path = os.path.join(audio_dir, audio_filename).replace('\\', '/')
                    image_path = os.path.join(image_dir, image_filename).replace('\\', '/') if image_filename else ''
                    
                    # Create or update song
                    song, created = Song.objects.get_or_create(
                        title=title,
                        artist=artist,
                        defaults={
                            'audio_file': audio_path,
                            'background_image': image_path
                        }
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f'Created: {song}')
                    else:
                        # Update existing song
                        song.audio_file = audio_path
                        song.background_image = image_path
                        song.save()
                        updated_count += 1
                        self.stdout.write(f'Updated: {song}')
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Row {row_num}: Error - {str(e)}')
                    )
                    error_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Import complete: {created_count} created, {updated_count} updated, {error_count} errors'
            )
        )
        
        total_songs = Song.objects.count()
        self.stdout.write(f'Total songs in database: {total_songs}')