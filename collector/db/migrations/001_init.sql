-- 초기 스키마 (설계 문서 §5.1)

CREATE TABLE IF NOT EXISTS entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL CHECK (kind IN ('mcp', 'skill', 'plugin', 'library')),
    slug text UNIQUE NOT NULL,
    canonical_name text NOT NULL,
    summary_ko text,
    usage_ko text,
    install_commands jsonb,
    tags text[] NOT NULL DEFAULT '{}',
    category text,
    repo_url text,
    homepage_url text,
    license text,
    stars integer NOT NULL DEFAULT 0,
    stars_delta_24h integer,
    stars_delta_7d integer,
    installs integer,
    npm_downloads_monthly integer,
    github_created_at timestamptz,
    github_pushed_at timestamptz,
    readme_hash text,
    entry_status text NOT NULL DEFAULT 'active',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_crawled_at timestamptz
);

CREATE TABLE IF NOT EXISTS appearances (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id uuid NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    source text NOT NULL,
    external_id text NOT NULL,
    url text,
    metrics jsonb NOT NULL DEFAULT '{}',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id uuid NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    source text NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    metrics jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS raw_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    external_id text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    fetched_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_cache (
    input_hash text PRIMARY KEY,
    model text NOT NULL,
    kind text NOT NULL,
    output jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL,
    kind text,
    status text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    stats jsonb NOT NULL DEFAULT '{}',
    error text
);

CREATE TABLE IF NOT EXISTS config (
    key text PRIMARY KEY,
    value jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entries_stars ON entries (stars DESC);
CREATE INDEX IF NOT EXISTS idx_entries_category ON entries (category);
CREATE INDEX IF NOT EXISTS idx_entries_tags ON entries USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_entries_repo_url ON entries (repo_url);

CREATE INDEX IF NOT EXISTS idx_metric_snapshots_entry_time
    ON metric_snapshots (entry_id, captured_at);

CREATE INDEX IF NOT EXISTS idx_raw_items_expiry ON raw_items (expires_at);

CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE entries ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(canonical_name, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(summary_ko, '')), 'B')
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_entries_search_tsv ON entries USING gin (search_tsv);
CREATE INDEX IF NOT EXISTS idx_entries_name_trgm ON entries USING gin (canonical_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_entries_summary_trgm ON entries USING gin (summary_ko gin_trgm_ops);
