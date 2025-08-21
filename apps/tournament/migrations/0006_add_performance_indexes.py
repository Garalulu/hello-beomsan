# Generated performance optimization migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournament', '0005_rename_artist_to_original_song'),
    ]

    operations = [
        # Add composite indexes for common query patterns
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS voting_session_user_status_idx ON voting_sessions (user_id, status);",
            reverse_sql="DROP INDEX IF EXISTS voting_session_user_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS voting_session_key_status_idx ON voting_sessions (session_key, status);",
            reverse_sql="DROP INDEX IF EXISTS voting_session_key_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS song_stats_idx ON songs (total_wins, total_picks);",
            reverse_sql="DROP INDEX IF EXISTS song_stats_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS vote_created_idx ON votes (created_at);",
            reverse_sql="DROP INDEX IF EXISTS vote_created_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS match_session_round_idx ON matches (session_id, round_number);",
            reverse_sql="DROP INDEX IF EXISTS match_session_round_idx;"
        ),
    ]