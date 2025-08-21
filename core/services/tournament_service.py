import random
import logging
from typing import List, Dict, Any, Optional, Tuple
from django.db import transaction
from django.db.models import Q
from django.core.cache import cache

logger = logging.getLogger(__name__)


class VotingSessionService:
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
        Create a new voting session with available songs (temporary test mode).
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
                # Normal case: randomly select 128 songs
                selected_songs = random.sample(all_songs, 128)
                logger.info(f"Creating normal session with 128 randomly selected songs")
            
            random.shuffle(selected_songs)
            
            # Create bracket structure
            bracket_data = VotingSessionService.generate_bracket_structure(selected_songs)
            if not bracket_data:
                logger.error("Failed to generate bracket structure")
                return None
            
            # Create voting session with database transaction
            with transaction.atomic():
                session = VotingSession.objects.create(
                    user=user,
                    session_key=session_key,
                    bracket_data=bracket_data,
                    current_round=1,
                    current_match=1,
                    status='ACTIVE'
                )
                logger.info(f"Created voting session {session.id} for user {user or 'anonymous'}")
            
            return session
            
        except Exception as e:
            logger.error(f"Error creating voting session: {type(e).__name__}: {str(e)}")
            return None
    
    @staticmethod
    def generate_bracket_structure(songs: List['Song']) -> Optional[Dict[str, Any]]:
        """
        Generate bracket structure for any number of songs.
        Returns None if unable to generate bracket.
        """
        try:
            if not songs:
                logger.error("Cannot generate bracket: No songs provided")
                return None
            
            bracket = {}
            current_songs = []
            
            # Safely extract song data
            for song in songs:
                try:
                    song_data = {
                        'id': str(song.id) if song.id else '',
                        'title': song.title or 'Unknown Song',
                        'original_song': song.original_song or ''
                    }
                    current_songs.append(song_data)
                except Exception as e:
                    logger.warning(f"Error processing song {song}: {e}")
                    continue
            
            if not current_songs:
                logger.error("No valid songs after processing")
                return None
            
            round_num = 1
            max_rounds = 10  # Safety limit to prevent infinite loops
            
            while len(current_songs) > 1 and round_num <= max_rounds:
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
                
                if not matches:
                    logger.error(f"No matches created for round {round_num}")
                    break
                
                bracket[f'round_{round_num}'] = matches
                current_songs = next_round_songs
                round_num += 1
            
            if round_num > max_rounds:
                logger.error("Bracket generation exceeded maximum rounds")
                return None
            
            logger.info(f"Generated bracket with {round_num - 1} rounds")
            return bracket
            
        except Exception as e:
            logger.error(f"Error generating bracket structure: {type(e).__name__}: {str(e)}")
            return None
    
    @staticmethod
    def get_current_match(session: 'VotingSession') -> Optional[Dict[str, Any]]:
        """
        Get current match data for voting.
        Returns None if unable to get match data.
        """
        from apps.tournament.models import Song
        
        try:
            if not session:
                logger.error("No session provided to get_current_match")
                return None
            
            if session.status != 'ACTIVE':
                logger.info(f"Session {session.id} is not active (status: {session.status})")
                return None
            
            match_data = session.get_current_match_data()
            if not match_data:
                logger.warning(f"No current match data for session {session.id}")
                return None
            
            # Safely get Song objects
            try:
                song1_id = match_data.get('song1', {}).get('id')
                song2_id = match_data.get('song2', {}).get('id')
                
                if not song1_id or not song2_id:
                    logger.error(f"Invalid song IDs in match data: song1={song1_id}, song2={song2_id}")
                    return None
                
                song1 = Song.objects.get(id=song1_id)
                song2 = Song.objects.get(id=song2_id)
                
            except Song.DoesNotExist as e:
                logger.error(f"Song not found: {e}")
                return None
            
            # Calculate progress safely
            try:
                progress = VotingSessionService.calculate_progress(session)
            except Exception as e:
                logger.warning(f"Error calculating progress: {e}")
                progress = {'completed_matches': 0, 'total_matches': 0, 'percentage': 0}
            
            return {
                'session_id': str(session.id),
                'round': session.current_round,
                'round_name': session.get_round_name(),
                'match': session.current_match,
                'match_progress': session.get_match_progress(),
                'song1': {
                    'id': str(song1.id),
                    'title': song1.title or 'Unknown Song',
                    'original_song': song1.original_song or '',
                    'audio_url': song1.audio_url or '',
                    'background_image_url': song1.background_image_url or ''
                },
                'song2': {
                    'id': str(song2.id),
                    'title': song2.title or 'Unknown Song',
                    'original_song': song2.original_song or '',
                    'audio_url': song2.audio_url or '',
                    'background_image_url': song2.background_image_url or ''
                },
                'total_rounds': len(session.bracket_data) if session.bracket_data else 0,
                'progress': progress
            }
            
        except Exception as e:
            logger.error(f"Error getting current match: {type(e).__name__}: {str(e)}")
            return None
    
    @staticmethod
    def cast_vote(session: 'VotingSession', chosen_song_id: str) -> bool:
        """
        Cast vote for a song and advance to next match.
        Returns True if successful, False otherwise.
        """
        import time
        from django.db import OperationalError, IntegrityError
        from apps.tournament.models import Song, Match, Vote
        
        if not session or not chosen_song_id:
            logger.error("Invalid session or song ID provided to cast_vote")
            return False
        
        if session.status != 'ACTIVE':
            logger.error(f"Cannot cast vote for inactive session {session.id} (status: {session.status})")
            return False
        
        # Retry mechanism for database locks
        for attempt in range(3):
            try:
                with transaction.atomic():
                    # Get current match data
                    match_data = session.get_current_match_data()
                    if not match_data:
                        logger.error(f"No match data available for session {session.id}")
                        return False
                    
                    # Validate song IDs exist in match data
                    song1_id = match_data.get('song1', {}).get('id')
                    song2_id = match_data.get('song2', {}).get('id')
                    
                    if not song1_id or not song2_id:
                        logger.error(f"Invalid match data structure for session {session.id}")
                        return False
                    
                    # Validate chosen song with optimized single query
                    try:
                        # Get all required songs in one query (unique IDs only)
                        unique_song_ids = list(set([chosen_song_id, song1_id, song2_id]))
                        songs = {str(s.id): s for s in Song.objects.filter(id__in=unique_song_ids).only('id', 'title', 'original_song')}
                        
                        if len(songs) != len(unique_song_ids):
                            logger.error(f"Not all songs found: expected {len(unique_song_ids)}, got {len(songs)}")
                            return False
                        
                        chosen_song = songs[chosen_song_id]
                        song1 = songs[song1_id]
                        song2 = songs[song2_id]
                        
                        if chosen_song_id not in [song1_id, song2_id]:
                            logger.error(f"Invalid song choice {chosen_song_id} for session {session.id}")
                            return False
                            
                    except (KeyError, ValueError) as e:
                        logger.error(f"Error validating songs: {e}")
                        return False
                    
                    # Check if match already exists (prevent duplicate votes)
                    existing_match = Match.objects.filter(
                        session=session,
                        round_number=session.current_round,
                        match_number=session.current_match
                    ).first()
                    
                    if existing_match:
                        logger.warning(f"Match already exists for session {session.id}, round {session.current_round}, match {session.current_match}")
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
                    
                    # Update song statistics safely
                    try:
                        chosen_song.total_wins += 1
                        chosen_song.total_picks += 1
                        chosen_song.save()
                        
                        loser = song2 if chosen_song == song1 else song1
                        loser.total_losses += 1
                        loser.total_picks += 1
                        loser.save()
                        
                        # Invalidate relevant caches when statistics change
                        from django.core.cache import cache
                        cache.delete_many([
                            'home_stats_total_votes',
                            'completed_tournaments_count'
                        ])
                        # Clear song stats cache for all pages and sorts
                        cache_patterns = ['song_stats_*']
                        for pattern in cache_patterns:
                            cache.delete_pattern(pattern) if hasattr(cache, 'delete_pattern') else None
                            
                    except Exception as e:
                        logger.warning(f"Error updating song statistics: {e}")
                        # Continue anyway as the vote was recorded
                    
                    # Update bracket data with winner
                    try:
                        round_key = f'round_{session.current_round}'
                        if round_key in session.bracket_data and session.current_match <= len(session.bracket_data[round_key]):
                            session.bracket_data[round_key][session.current_match - 1]['winner'] = {
                                'id': str(chosen_song.id),
                                'title': chosen_song.title or 'Unknown Song',
                                'original_song': chosen_song.original_song or ''
                            }
                            session.bracket_data[round_key][session.current_match - 1]['completed'] = True
                        else:
                            logger.error(f"Invalid bracket structure for session {session.id}")
                            return False
                    except Exception as e:
                        logger.error(f"Error updating bracket data: {e}")
                        return False
                    
                    # Update next round if this round is complete
                    try:
                        VotingSessionService.update_next_round(session)
                    except Exception as e:
                        logger.warning(f"Error updating next round: {e}")
                        # Continue anyway
                    
                    # Advance to next match
                    try:
                        session.advance_to_next_match()
                    except Exception as e:
                        logger.error(f"Error advancing to next match: {e}")
                        return False
                
                logger.info(f"Vote cast successfully for session {session.id}, song {chosen_song_id}")
                return True
                
            except IntegrityError as e:
                logger.error(f"Database integrity error in cast_vote: {e}")
                return False
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < 2:
                    logger.warning(f"Database locked, retrying attempt {attempt + 1}")
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    logger.error(f"Database error after {attempt + 1} attempts: {str(e)}")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error in cast_vote (attempt {attempt + 1}): {type(e).__name__}: {str(e)}")
                if attempt < 2:
                    time.sleep(0.1)
                    continue
                return False
        
        logger.error(f"Failed to cast vote after 3 attempts for session {session.id}")
        return False
    
    @staticmethod
    def update_next_round(session: 'VotingSession'):
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
    def calculate_progress(session: 'VotingSession') -> Dict[str, Any]:
        """
        Calculate voting progress percentage with optimized JSON processing.
        """
        # Use cached property if available
        if hasattr(session, 'progress_data'):
            cached_data = session.progress_data
            return {
                'completed_matches': cached_data['matches_completed'],
                'total_matches': cached_data['matches_total'],
                'percentage': cached_data['percentage'],
                'current_round': session.current_round,
                'total_rounds': len(session.bracket_data)
            }
        
        # Fallback to original calculation
        total_matches = 0
        completed_matches = 0
        
        # Optimize JSON processing by reducing iterations
        bracket_items = session.bracket_data.items() if session.bracket_data else []
        
        for round_key, matches in bracket_items:
            match_count = len(matches)
            total_matches += match_count
            # Use list comprehension for better performance
            completed_matches += sum(1 for match in matches if match.get('completed', False))
        
        percentage = (completed_matches / total_matches * 100) if total_matches > 0 else 0
        
        return {
            'completed_matches': completed_matches,
            'total_matches': total_matches,
            'percentage': round(percentage, 1),
            'current_round': session.current_round,
            'total_rounds': len(bracket_items)
        }
    
    @staticmethod
    def get_or_create_session(user=None, session_key=None) -> Tuple[Optional['VotingSession'], bool]:
        """
        Get existing session (completed or active) or create new one.
        Priority: COMPLETED (show results) -> ACTIVE (continue voting) -> CREATE NEW
        Returns (session, is_existing) or (None, False) if error.
        """
        from apps.tournament.models import VotingSession
        
        try:
            existing_session = None
            
            if user:
                try:
                    # First check for COMPLETED sessions (to show results)
                    existing_session = VotingSession.objects.filter(
                        user=user,
                        status='COMPLETED'
                    ).order_by('-updated_at').first()
                    
                    if not existing_session:
                        # Then check for ACTIVE sessions (to continue voting)
                        existing_session = VotingSession.objects.filter(
                            user=user,
                            status='ACTIVE'
                        ).first()
                        
                except Exception as e:
                    logger.warning(f"Error querying user sessions: {e}")
            elif session_key:
                try:
                    # First check for COMPLETED sessions (to show results)
                    existing_session = VotingSession.objects.filter(
                        session_key=session_key,
                        status='COMPLETED'
                    ).order_by('-updated_at').first()
                    
                    if not existing_session:
                        # Then check for ACTIVE sessions (to continue voting)
                        existing_session = VotingSession.objects.filter(
                            session_key=session_key,
                            status='ACTIVE'
                        ).first()
                        
                except Exception as e:
                    logger.warning(f"Error querying anonymous sessions: {e}")
            
            if existing_session:
                logger.info(f"Found existing {existing_session.status} session {existing_session.id}")
                return existing_session, True  # existing=True
            else:
                # Create new session only if no existing session found
                new_session = VotingSessionService.create_voting_session(user, session_key)
                if new_session:
                    logger.info(f"Created new session {new_session.id}")
                    return new_session, False  # existing=False
                else:
                    logger.error("Failed to create new voting session")
                    return None, False
                    
        except Exception as e:
            logger.error(f"Error in get_or_create_session: {type(e).__name__}: {str(e)}")
            return None, False