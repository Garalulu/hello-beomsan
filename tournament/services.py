import random
from typing import List, Dict, Any
from django.db import transaction
from .models import Song, VotingSession, Match, Vote


class VotingSessionService:
    @staticmethod
    def create_voting_session(user=None, session_key=None) -> VotingSession:
        """
        Create a new voting session with available songs (temporary test mode).
        """
        # Get all available songs
        all_songs = list(Song.objects.all())
        
        if len(all_songs) < 128:
            raise ValueError(f"Need at least 128 songs, but only {len(all_songs)} available")
        
        # Randomly select 128 songs for the tournament
        selected_songs = random.sample(all_songs, 128)
        
        random.shuffle(selected_songs)
        
        # Create bracket structure
        bracket_data = VotingSessionService.generate_bracket_structure(selected_songs)
        
        # Create voting session
        session = VotingSession.objects.create(
            user=user,
            session_key=session_key,
            bracket_data=bracket_data,
            current_round=1,
            current_match=1,
            status='ACTIVE'
        )
        
        return session
    
    @staticmethod
    def generate_bracket_structure(songs: List[Song]) -> Dict[str, Any]:
        """
        Generate bracket structure for any number of songs.
        """
        bracket = {}
        current_songs = [{'id': str(song.id), 'title': song.title, 'artist': song.artist} for song in songs]
        round_num = 1
        
        while len(current_songs) > 1:
            matches = []
            next_round_songs = []
            
            # Create matches for current round
            for i in range(0, len(current_songs), 2):
                if i + 1 < len(current_songs):
                    match = {
                        'match_number': len(matches) + 1,
                        'song1': current_songs[i],
                        'song2': current_songs[i + 1],
                        'winner': None,
                        'completed': False
                    }
                    matches.append(match)
                    # Placeholder for winner (will be filled during voting)
                    next_round_songs.append({'placeholder': True, 'from_match': len(matches)})
                else:
                    # Odd number of songs, this one advances automatically
                    next_round_songs.append(current_songs[i])
            
            bracket[f'round_{round_num}'] = matches
            current_songs = next_round_songs
            round_num += 1
        
        return bracket
    
    @staticmethod
    def get_current_match(session: VotingSession) -> Dict[str, Any]:
        """
        Get current match data for voting.
        """
        match_data = session.get_current_match_data()
        if not match_data:
            return None
        
        # Get Song objects
        song1 = Song.objects.get(id=match_data['song1']['id'])
        song2 = Song.objects.get(id=match_data['song2']['id'])
        
        return {
            'session_id': str(session.id),
            'round': session.current_round,
            'round_name': session.get_round_name(),
            'match': session.current_match,
            'match_progress': session.get_match_progress(),
            'song1': {
                'id': str(song1.id),
                'title': song1.title,
                'artist': song1.artist,
                'audio_url': song1.audio_url,
                'background_image_url': song1.background_image_url
            },
            'song2': {
                'id': str(song2.id),
                'title': song2.title,
                'artist': song2.artist,
                'audio_url': song2.audio_url,
                'background_image_url': song2.background_image_url
            },
            'total_rounds': len(session.bracket_data),
            'progress': VotingSessionService.calculate_progress(session)
        }
    
    @staticmethod
    def cast_vote(session: VotingSession, chosen_song_id: str) -> bool:
        """
        Cast vote for a song and advance to next match.
        """
        import time
        from django.db import OperationalError
        
        # Retry mechanism for database locks
        for attempt in range(3):
            try:
                # Get current match data
                match_data = session.get_current_match_data()
                if not match_data:
                    print("No match data available")
                    return False
                
                # Validate chosen song
                chosen_song = Song.objects.get(id=chosen_song_id)
                song1 = Song.objects.get(id=match_data['song1']['id'])
                song2 = Song.objects.get(id=match_data['song2']['id'])
                
                if chosen_song not in [song1, song2]:
                    print(f"Invalid song choice: {chosen_song_id}")
                    return False
                
                # Create match record
                match = Match.objects.create(
                    session=session,
                    round_number=session.current_round,
                    match_number=session.current_match,
                    song1=song1,
                    song2=song2,
                    winner=chosen_song
                )
                
                # Create vote record
                Vote.objects.create(
                    match=match,
                    session=session,
                    chosen_song=chosen_song
                )
                
                # Update song statistics
                chosen_song.total_wins += 1
                chosen_song.total_picks += 1
                chosen_song.save()
                
                loser = song2 if chosen_song == song1 else song1
                loser.total_losses += 1
                loser.total_picks += 1
                loser.save()
                
                # Update bracket data with winner
                round_key = f'round_{session.current_round}'
                session.bracket_data[round_key][session.current_match - 1]['winner'] = {
                    'id': str(chosen_song.id),
                    'title': chosen_song.title,
                    'artist': chosen_song.artist
                }
                session.bracket_data[round_key][session.current_match - 1]['completed'] = True
                
                # Update next round if this round is complete
                VotingSessionService.update_next_round(session)
                
                # Advance to next match
                session.advance_to_next_match()
                
                return True
                
            except OperationalError as e:
                if "database is locked" in str(e) and attempt < 2:
                    print(f"Database locked, retrying attempt {attempt + 1}")
                    time.sleep(0.1)  # Wait 100ms before retry
                    continue
                else:
                    print(f"Database error after {attempt + 1} attempts: {str(e)}")
                    return False
            except Exception as e:
                print(f"Unexpected error in cast_vote: {type(e).__name__}: {str(e)}")
                return False
        
        return False
    
    @staticmethod
    def update_next_round(session: VotingSession):
        """
        Update next round matches when current round is complete.
        """
        current_round_key = f'round_{session.current_round}'
        current_matches = session.bracket_data[current_round_key]
        
        # Check if all matches in current round are completed
        all_completed = all(match['completed'] for match in current_matches)
        
        if all_completed:
            next_round_key = f'round_{session.current_round + 1}'
            if next_round_key in session.bracket_data:
                # Update next round with winners
                winners = [match['winner'] for match in current_matches if match['winner']]
                next_round_matches = session.bracket_data[next_round_key]
                
                # Pair up winners for next round
                for i, match in enumerate(next_round_matches):
                    if i * 2 < len(winners):
                        match['song1'] = winners[i * 2]
                    if i * 2 + 1 < len(winners):
                        match['song2'] = winners[i * 2 + 1]
    
    @staticmethod
    def calculate_progress(session: VotingSession) -> Dict[str, Any]:
        """
        Calculate voting progress percentage.
        """
        total_matches = 0
        completed_matches = 0
        
        for round_key, matches in session.bracket_data.items():
            total_matches += len(matches)
            completed_matches += sum(1 for match in matches if match.get('completed', False))
        
        percentage = (completed_matches / total_matches * 100) if total_matches > 0 else 0
        
        return {
            'completed_matches': completed_matches,
            'total_matches': total_matches,
            'percentage': round(percentage, 1),
            'current_round': session.current_round,
            'total_rounds': len(session.bracket_data)
        }
    
    @staticmethod
    def get_or_create_session(user=None, session_key=None):
        """
        Get existing active session or create new one.
        """
        # Try to find existing active session
        if user:
            existing_session = VotingSession.objects.filter(
                user=user,
                status='ACTIVE'
            ).first()
        else:
            existing_session = VotingSession.objects.filter(
                session_key=session_key,
                status='ACTIVE'
            ).first()
        
        if existing_session:
            return existing_session, True  # existing=True
        else:
            return VotingSessionService.create_voting_session(user, session_key), False  # existing=False