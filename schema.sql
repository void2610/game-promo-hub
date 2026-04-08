PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS games (
    id              TEXT PRIMARY KEY,
    name_ja         TEXT NOT NULL,
    name_en         TEXT,
    genre           TEXT,
    platform        TEXT DEFAULT 'Steam',
    status          TEXT DEFAULT 'development',
    steam_url       TEXT,
    elevator_ja     TEXT,
    elevator_en     TEXT,
    hashtags        TEXT,
    target_audience TEXT,
    circle          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS progress_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    log_date        DATE NOT NULL,
    milestone       TEXT,
    content         TEXT NOT NULL,
    appeal_note     TEXT,
    excitement      INTEGER DEFAULT 2,
    tweetable       INTEGER DEFAULT 1,
    tweeted         INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appeal_points (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    category        TEXT,
    priority        INTEGER DEFAULT 2,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    promo_tips      TEXT,
    last_used_at    DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    filename        TEXT NOT NULL,
    asset_type      TEXT,
    description     TEXT,
    recommended_for TEXT,
    local_path      TEXT NOT NULL,
    width           INTEGER,
    height          INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tweets (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id             TEXT UNIQUE,
    game_id              TEXT NOT NULL REFERENCES games(id),
    lang                 TEXT,
    content              TEXT NOT NULL,
    asset_id             INTEGER REFERENCES assets(id),
    tone                 TEXT,
    strategy_note        TEXT,
    posted_at            DATETIME,
    tweet_url            TEXT,
    impressions          INTEGER,
    likes                INTEGER,
    retweets             INTEGER,
    replies              INTEGER,
    analytics_fetched_at DATETIME,
    approved_by          TEXT,
    reply_to_tweet_id    TEXT,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tweet_drafts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_group_id       TEXT,
    game_id              TEXT NOT NULL REFERENCES games(id),
    lang                 TEXT,
    content              TEXT NOT NULL,
    asset_id             INTEGER REFERENCES assets(id),
    tone                 TEXT,
    strategy_note        TEXT,
    asset_reason         TEXT,
    source_progress_ids  TEXT,
    source_appeal_ids    TEXT,
    status               TEXT DEFAULT 'pending',
    discord_msg_id       TEXT,
    approved_by          TEXT,
    approved_at          DATETIME,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    period          TEXT,
    best_time_slot  TEXT,
    best_tone       TEXT,
    best_asset_type TEXT,
    strategy_note   TEXT,
    raw_analysis    TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schedule_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_time   TEXT NOT NULL UNIQUE,
    enabled     INTEGER DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_progress_logs_game_date
    ON progress_logs(game_id, log_date DESC);

CREATE INDEX IF NOT EXISTS idx_appeal_points_game_priority
    ON appeal_points(game_id, priority DESC, last_used_at ASC);

CREATE INDEX IF NOT EXISTS idx_tweets_game_posted_at
    ON tweets(game_id, posted_at DESC);

CREATE INDEX IF NOT EXISTS idx_tweet_drafts_status_group
    ON tweet_drafts(status, draft_group_id, approved_at ASC, created_at ASC);
