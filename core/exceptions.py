"""
Custom exceptions for the application.
"""


class TournamentError(Exception):
    """Base exception for tournament-related errors"""
    pass


class VotingSessionError(TournamentError):
    """Exception for voting session-related errors"""
    pass


class InsufficientSongsError(VotingSessionError):
    """Exception when there aren't enough songs to create a tournament"""
    pass


class SessionNotFoundError(VotingSessionError):
    """Exception when a voting session is not found"""
    pass


class InvalidVoteError(VotingSessionError):
    """Exception for invalid vote attempts"""
    pass


class AuthenticationError(Exception):
    """Base exception for authentication-related errors"""
    pass


class OAuthError(AuthenticationError):
    """Exception for OAuth-related errors"""
    pass


class UserCreationError(AuthenticationError):
    """Exception when user creation fails"""
    pass


class ValidationError(Exception):
    """Exception for validation errors"""
    pass


class SecurityError(Exception):
    """Exception for security-related violations"""
    pass


class RateLimitError(SecurityError):
    """Exception when rate limits are exceeded"""
    pass