-- GitHub 전체 랭킹 참조 (EvanLi/Github-Ranking 일일 스냅샷) — 엔트리와 분리된 레퍼런스 데이터
CREATE TABLE IF NOT EXISTS rank_reference (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date date NOT NULL,
    repo_full_name text NOT NULL,
    rank integer NOT NULL,
    stars integer NOT NULL,
    language text,
    description text,
    UNIQUE (snapshot_date, repo_full_name)
);
CREATE INDEX IF NOT EXISTS idx_rank_reference_repo
    ON rank_reference (repo_full_name, snapshot_date DESC);
