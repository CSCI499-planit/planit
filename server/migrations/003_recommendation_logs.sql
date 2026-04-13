-- TODO-DB3: Add recommendation_logs table for LTR training data
CREATE TABLE IF NOT EXISTS recommendation_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       TEXT NOT NULL,
    place_id      TEXT NOT NULL,
    rank_position INT NOT NULL,
    features      JSONB NOT NULL,
    final_score   FLOAT NOT NULL,
    outcome       TEXT CHECK (outcome IN ('added', 'skipped', 'saved')),
    outcome_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_reclogs_user_id ON recommendation_logs(user_id);
CREATE INDEX idx_reclogs_outcome  ON recommendation_logs(outcome)
    WHERE outcome IS NOT NULL;
