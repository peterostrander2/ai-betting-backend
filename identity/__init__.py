# Identity Resolution Module
# Unified Player ID Resolver for cross-API player matching

from .name_normalizer import normalize_player_name, normalize_team_name
from .player_resolver import (
    resolve_player,
    ResolvedPlayer,
    get_player_resolver,
)
from .player_index_store import (
    PlayerIndexStore,
    get_player_index,
)

__all__ = [
    'normalize_player_name',
    'normalize_team_name',
    'resolve_player',
    'ResolvedPlayer',
    'get_player_resolver',
    'PlayerIndexStore',
    'get_player_index',
]
