"""
Implicit feedback interaction logging.
Called whenever a user views, saves, or adds a place to their itinerary.
These events feed into the CF interaction matrix at retrain time.

EVENT_RATINGS is the single source of truth for event-to-rating mapping.
ml/models/user_profiler.py imports from here — do not redefine it there.
"""
from server.config.db import supabase

INTERACTIONS_TABLE = 'user_interactions'

# maps each event type to an implicit rating (1–5 scale)
EVENT_RATINGS: dict[str, float] = {
    "like":              4.5,
    "unlike":            1.0,
    "itinerary_like":    5.0,
    "itinerary_dislike": 1.0,
}


def log_interaction(
    user_id:    str,
    place_id:   str,
    event_type: str,
    metadata:   dict | None = None,
    client=supabase,
):
    if event_type not in EVENT_RATINGS:
        raise ValueError(
            f"Unknown event_type '{event_type}'. Valid: {list(EVENT_RATINGS)}"
        )
    return (
        client.table(INTERACTIONS_TABLE)
        .insert({
            "user_id":    user_id,
            "place_id":   place_id,
            "event_type": event_type,
            "metadata":   metadata or {},
        })
        .execute()
    )


def get_interactions(user_id: str, client=supabase):
    return (
        client.table(INTERACTIONS_TABLE)
        .select('*')
        .eq('user_id', user_id)
        .execute()
    )


def get_all_interactions(client=supabase):
    return (
        client.table(INTERACTIONS_TABLE)
        .select('*')
        .execute()
    )
