from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Promote specific users to admin status'

    def handle(self, *args, **options):
        admin_usernames = ['Garalulu']  # Add more usernames here if needed
        
        self.stdout.write(f'Checking for admin users to promote: {admin_usernames}')
        
        for username in admin_usernames:
            try:
                # Try to find user by osu username first (in profile)
                from apps.tournament.models import UserProfile
                try:
                    profile = UserProfile.objects.get(osu_username=username)
                    user = profile.user
                except UserProfile.DoesNotExist:
                    # Fallback to Django username
                    try:
                        user = User.objects.get(username=username)
                    except User.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f'User "{username}" not found. They need to login first.'
                            )
                        )
                        continue
                
                # Make user staff and superuser
                user.is_staff = True
                user.is_superuser = True
                user.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully promoted "{username}" to admin'
                    )
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error promoting "{username}": {str(e)}'
                    )
                )