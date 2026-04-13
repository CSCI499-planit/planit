-- TODO-DB2: Add user_interactions table for implicit feedback
CREATE TABLE IF NOT EXISTS user_interactions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    place_id    TEXT NOT NULL,
    event_type  TEXT NOT NULL
                    CHECK (event_type IN ('view','save','unsave','itinerary_add','swipe_pass')),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_user_interactions_user_id ON user_interactions(user_id);
CREATE INDEX idx_user_interactions_place_id ON user_interactions(place_id);
