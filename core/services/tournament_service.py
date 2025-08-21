"""
Tournament business logic service.
Handles voting session creation, management, and voting logic.
"""
import random
import logging
from typing import List, Dict, Any, Optional, Tuple
from django.db import transaction
from django.db.models import Q
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TournamentService:
    """Service for managing tournament operations."""
    
    @staticmethod
    def get_cached_completed_tournaments_count():
        """Get cached count of completed tournaments to avoid repeated queries"""
        from apps.tournament.models import VotingSession
        
        cache_key = 'completed_tournaments_count'
        count = cache.get(cache_key)
        
        if count is None:
            count = VotingSession.objects.filter(status='COMPLETED').count()
            cache.set(cache_key, count, timeout=300)  # Cache for 5 minutes
        
        return count
    
    @staticmethod
    def create_voting_session(user=None, session_key=None) -> Optional['VotingSession']:
        """
        Create a new voting session with available songs.
        Returns None if unable to create session due to errors.
        """
        from apps.tournament.models import Song, VotingSession
        
        try:
            # Get all available songs
            all_songs = list(Song.objects.all())
            
            if len(all_songs) < 1:
                logger.error("Cannot create voting session: No songs in database")
                return None
            
            # For testing: use all available songs (repeat if needed to make pairs)
            if len(all_songs) == 1:
                # Special case: duplicate the single song to create a "tournament"
                selected_songs = all_songs * 2  # Make 2 copies for testing
                logger.info(f"Creating test session with 1 song duplicated")
            elif len(all_songs) < 128:
                # Use all available songs
                selected_songs = all_songs.copy()
                # Pad to even number if needed
                if len(selected_songs) % 2 != 0:
                    selected_songs.append(all_songs[0])  # Duplicate one song
                logger.info(f"Creating session with {len(all_songs)} songs (padded to {len(selected_songs)})")
            else:
                # Standard tournament mode: randomly select 128 songs
                selected_songs = random.sample(all_songs, 128)
                logger.info(f"Creating session with 128 randomly selected songs")
            
            # Create the tournament bracket structure
            bracket_data = TournamentService._create_tournament_bracket(selected_songs)
            
            # Create the voting session
            with transaction.atomic():
                session = VotingSession.objects.create(
                    user=user,
                    session_key=session_key,
                    bracket_data=bracket_data,
                    current_round=1,
                    current_match=1,
                    status='ACTIVE'
                )
                
                logger.info(f"Created voting session {session.id} with {len(selected_songs)} songs")
                return session
                
        except Exception as e:
            logger.error(f"Error creating voting session: {str(e)}")
            return None
    
    @staticmethod
    def _create_tournament_bracket(songs: List['Song']) -> Dict[str, Any]:
        """Create a tournament bracket structure from selected songs."""
        bracket = {}
        current_songs = [TournamentService._song_to_dict(song) for song in songs]
        round_num = 1
        
        # Create rounds until we have a winner
        while len(current_songs) > 1:
            # Create matches for current round
            matches = []
            for i in range(0, len(current_songs), 2):
                if i + 1 < len(current_songs):
                    match = {
                        'song1': current_songs[i],
                        'song2': current_songs[i + 1],
                        'winner': None
                    }
                    matches.append(match)
                else:
                    # Odd number of songs, bye for the last one
                    matches.append({
                        'song1': current_songs[i],
                        'song2': None,
                        'winner': current_songs[i]  # Automatic advancement
                    })
            
            bracket[f'round_{round_num}'] = matches
            
            # Prepare for next round (will be filled as matches are completed)
            if round_num > 1:  # Don't create next round for first round yet
                current_songs = [None] * len(matches)  # Placeholders for winners
            else:
                current_songs = [None] * len(matches)  # Placeholders for winners
            
            round_num += 1
            
            # Safety break for very small tournaments
            if round_num > 10:
                break
        
        return bracket
    
    @staticmethod
    def _song_to_dict(song: 'Song') -> Dict[str, Any]:
        """Convert Song model to dictionary for JSON storage."""
        return {
            'id': str(song.id),
            'title': song.title,
            'original_song': song.original_song or '',
            'audio_url': song.audio_url,
            'background_image_url': song.background_image_url or '',
        }
    
    @staticmethod
    def get_or_create_session(user=None, session_key=None) -> Optional['VotingSession']:
        """Get existing active session or create new one."""
        from apps.tournament.models import VotingSession
        
        try:
            # Look for existing active session
            query = Q(status='ACTIVE')
            if user and user.is_authenticated:
                query &= Q(user=user)
            else:
                query &= Q(session_key=session_key)
            
            existing_session = VotingSession.objects.filter(query).first()
            
            if existing_session:
                logger.info(f"Found existing session: {existing_session.id}")
                return existing_session
            
            # Create new session
            logger.info("Creating new voting session")
            return TournamentService.create_voting_session(user=user, session_key=session_key)
            
        except Exception as e:
            logger.error(f"Error getting/creating session: {str(e)}")
            return None
    
    @staticmethod
    def get_current_match(session: 'VotingSession') -> Optional[Dict[str, Any]]:
        """Get current match data for a session."""
        if session.status == 'COMPLETED':
            return None
        
        match_data = session.get_current_match_data()
        if not match_data:
            return None
        
        return {
            'session_id': str(session.id),
            'song1': match_data['song1'],
            'song2': match_data['song2'],
            'round_name': session.get_round_name(),
            'match_progress': session.get_match_progress(),
            'progress': session.progress_data
        }
    
    @staticmethod
    @transaction.atomic
    def cast_vote(session_id: str, chosen_song_id: str, user=None, session_key=None) -> Dict[str, Any]:
        """Cast a vote and advance the tournament."""
        from apps.tournament.models import VotingSession, Song, Match, Vote
        
        try:
            session = VotingSession.objects.select_for_update().get(id=session_id)
            
            if session.status != 'ACTIVE':
                return {'success': False, 'error': 'Session is not active'}
            
            # Get current match
            current_match_data = session.get_current_match_data()
            if not current_match_data:
                return {'success': False, 'error': 'No current match found'}
            
            # Validate the chosen song is part of current match
            song1_id = current_match_data['song1']['id']
            song2_id = current_match_data['song2']['id']
            
            if chosen_song_id not in [song1_id, song2_id]:
                return {'success': False, 'error': 'Invalid song selection'}
            
            # Get the chosen song
            chosen_song = Song.objects.get(id=chosen_song_id)
            
            # Update song statistics
            song1 = Song.objects.get(id=song1_id)
            song2 = Song.objects.get(id=song2_id)
            
            # Increment pick counts for both songs
            song1.total_picks += 1
            song2.total_picks += 1
            
            # Increment win count for chosen song and loss for the other
            if chosen_song_id == song1_id:
                song1.total_wins += 1
                song2.total_losses += 1
            else:
                song2.total_wins += 1
                song1.total_losses += 1
            
            song1.save()
            song2.save()
            
            # Create match and vote records
            match = Match.objects.create(
                session=session,
                round_number=session.current_round,
                match_number=session.current_match,
                song1=song1,
                song2=song2,
                winner=chosen_song
            )
            
            Vote.objects.create(
                match=match,
                session=session,
                chosen_song=chosen_song
            )
            
            # Update bracket with winner
            round_key = f'round_{session.current_round}'
            if round_key in session.bracket_data:
                matches = session.bracket_data[round_key]
                if session.current_match <= len(matches):
                    matches[session.current_match - 1]['winner'] = TournamentService._song_to_dict(chosen_song)
            
            # Advance to next match/round and check for tournament completion
            was_completed = session.status == 'COMPLETED'
            session.advance_to_next_match()
            is_now_completed = session.status == 'COMPLETED'
            
            response_data = {
                'success': True,
                'completed': is_now_completed,
                'next_match': None
            }
            
            # If tournament just completed, handle final logic
            if not was_completed and is_now_completed:
                response_data['completed'] = True
                # Invalidate completed tournaments cache
                cache.delete('completed_tournaments_count')
            else:
                # Get next match data
                next_match = TournamentService.get_current_match(session)
                response_data['next_match'] = next_match
            
            return response_data
            
        except VotingSession.DoesNotExist:
            return {'success': False, 'error': 'Session not found'}
        except Song.DoesNotExist:
            return {'success': False, 'error': 'Song not found'}
        except Exception as e:
            logger.error(f"Error casting vote: {str(e)}")
            return {'success': False, 'error': 'An error occurred while casting vote'}


# Backward compatibility alias
VotingSessionService = TournamentService