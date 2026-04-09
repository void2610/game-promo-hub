-- 外部キー制約を有効にする（SQLite はデフォルトで無効）
PRAGMA foreign_keys = ON;

-- ゲーム基本情報テーブル
-- hashtags / target_audience は JSON 配列文字列として格納する
CREATE TABLE IF NOT EXISTS games (
    id              TEXT PRIMARY KEY,       -- ゲームの一意な識別子（例: niwa-kobito）
    name_ja         TEXT NOT NULL,          -- 日本語タイトル
    name_en         TEXT,                   -- 英語タイトル
    genre           TEXT,                   -- ジャンル
    platform        TEXT DEFAULT 'Steam',   -- 販売プラットフォーム
    status          TEXT DEFAULT 'development', -- 開発状態（development / released など）
    steam_url       TEXT,                   -- Steam ストアページ URL
    elevator_ja     TEXT,                   -- 日本語エレベーターピッチ
    elevator_en     TEXT,                   -- 英語エレベーターピッチ
    hashtags        TEXT,                   -- ハッシュタグ一覧（JSON 配列）
    target_audience TEXT,                   -- ターゲット層（JSON 配列）
    circle          TEXT,                   -- 制作サークル名
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 進捗ログテーブル
-- tweetable=1 かつ tweeted=0 のものがツイート候補として使われる
CREATE TABLE IF NOT EXISTS progress_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    log_date        DATE NOT NULL,          -- 進捗日付（YYYY-MM-DD）
    milestone       TEXT,                   -- マイルストーン名（任意）
    content         TEXT NOT NULL,          -- 進捗内容
    appeal_note     TEXT,                   -- 宣伝に使えるヒント（任意）
    excitement      INTEGER DEFAULT 2,      -- 興奮度（1–3）
    tweetable       INTEGER DEFAULT 1,      -- ツイート候補に含めるか（0/1）
    tweeted         INTEGER DEFAULT 0,      -- ツイート済みか（0/1）
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- アピールポイントテーブル
-- priority が高く last_used_at が古いものが優先して使われる
CREATE TABLE IF NOT EXISTS appeal_points (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    category        TEXT,                   -- カテゴリ（mechanics / art / story / technical など）
    priority        INTEGER DEFAULT 2,      -- 優先度（1–3）
    title           TEXT NOT NULL,          -- アピールポイントのタイトル
    content         TEXT NOT NULL,          -- 詳細内容
    promo_tips      TEXT,                   -- 宣伝ヒント（任意）
    last_used_at    DATETIME,               -- 最後にツイートで使用した日時
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 素材ファイルテーブル
-- ローカルパスに保存されたファイルのメタデータを管理する
CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    filename        TEXT NOT NULL,          -- 元のファイル名
    asset_type      TEXT,                   -- ファイル種別（png / gif / mp4 など）
    description     TEXT,                   -- 素材の説明
    recommended_for TEXT,                   -- 推奨用途（initial / technical / any など）
    local_path      TEXT NOT NULL,          -- ローカルファイルパス
    width           INTEGER,               -- 横幅（ピクセル）
    height          INTEGER,               -- 縦幅（ピクセル）
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 投稿済みツイートテーブル
-- Twitter/X への投稿履歴とアナリティクスデータを管理する
CREATE TABLE IF NOT EXISTS tweets (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id             TEXT UNIQUE,        -- Twitter/X のツイート ID
    game_id              TEXT NOT NULL REFERENCES games(id),
    lang                 TEXT,              -- 言語（ja / en）
    content              TEXT NOT NULL,     -- ツイート本文
    asset_id             INTEGER REFERENCES assets(id),  -- 添付素材
    tone                 TEXT,              -- 使用したトーン
    strategy_note        TEXT,             -- 生成時の戦略メモ
    posted_at            DATETIME,          -- 投稿日時（JST ISO 8601）
    tweet_url            TEXT,              -- ツイートの URL
    impressions          INTEGER,           -- インプレッション数
    likes                INTEGER,           -- いいね数
    retweets             INTEGER,           -- リツイート数
    replies              INTEGER,           -- リプライ数
    analytics_fetched_at DATETIME,          -- メトリクスを最後に取得した日時
    approved_by          TEXT,              -- 承認した Discord ユーザー ID
    reply_to_tweet_id    TEXT,              -- リプライ元のツイート ID（スレッド用）
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ツイート下書きテーブル
-- pending → approved → posted / rejected の状態遷移で管理する
-- draft_group_id が同じ下書きは ja/en ペアとしてまとめて扱われる
CREATE TABLE IF NOT EXISTS tweet_drafts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_group_id       TEXT,              -- ja/en ペアをまとめるグループ ID（UUID4 ハッシュ）
    game_id              TEXT NOT NULL REFERENCES games(id),
    mode                 TEXT,              -- 生成モード（progress / appeal / random など）
    lang                 TEXT,              -- 言語（ja / en）
    content              TEXT NOT NULL,     -- 下書き本文
    asset_id             INTEGER REFERENCES assets(id),  -- 推奨素材
    tone                 TEXT,              -- 使用したトーン
    strategy_note        TEXT,             -- 生成時の戦略メモ
    asset_reason         TEXT,             -- 素材を採用した理由
    source_progress_ids  TEXT,             -- 使用した進捗ログの ID リスト（JSON 配列）
    source_appeal_ids    TEXT,             -- 使用したアピールポイントの ID リスト（JSON 配列）
    status               TEXT DEFAULT 'pending',  -- ステータス（pending / approved / posted / rejected）
    discord_msg_id       TEXT,             -- 承認ボタンを表示した Discord メッセージ ID
    approved_by          TEXT,             -- 承認した Discord ユーザー ID
    approved_at          DATETIME,          -- 承認日時
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- アナリティクスサマリーテーブル
-- 月次でまとめた分析レポートを保存する
CREATE TABLE IF NOT EXISTS analytics_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id),
    period          TEXT,                   -- 分析対象期間（例: "2026-04"）
    best_time_slot  TEXT,                   -- 最も効果的な投稿時間帯
    best_tone       TEXT,                   -- 最も効果的なトーン
    best_asset_type TEXT,                   -- 最も効果的な素材タイプ
    strategy_note   TEXT,                   -- 次の月に向けた戦略提案
    raw_analysis    TEXT,                   -- LLM が返した分析結果の生 JSON
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 定期投稿スロットテーブル
-- enabled=1 のスロットがスケジューラのポーリング対象になる
CREATE TABLE IF NOT EXISTS schedule_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_time   TEXT NOT NULL UNIQUE,       -- 投稿時刻（HH:MM 形式、JST）
    enabled     INTEGER DEFAULT 1,          -- 有効フラグ（0/1）
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- インデックス: 進捗ログをゲーム・日付で高速検索
CREATE INDEX IF NOT EXISTS idx_progress_logs_game_date
    ON progress_logs(game_id, log_date DESC);

-- インデックス: アピールポイントをゲーム・優先度・使用日時で高速検索
CREATE INDEX IF NOT EXISTS idx_appeal_points_game_priority
    ON appeal_points(game_id, priority DESC, last_used_at ASC);

-- インデックス: ツイートをゲーム・投稿日時で高速検索
CREATE INDEX IF NOT EXISTS idx_tweets_game_posted_at
    ON tweets(game_id, posted_at DESC);

-- インデックス: 下書きをステータス・グループ・承認日時で高速検索（キュー処理に使用）
CREATE INDEX IF NOT EXISTS idx_tweet_drafts_status_group
    ON tweet_drafts(status, draft_group_id, approved_at ASC, created_at ASC);
