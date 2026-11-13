-- appearances.entry_id 인덱스 — export의 상관 EXISTS(소스별 가치 판정)가
-- 행마다 풀스캔하지 않도록. metric_snapshots는 captured_at 단독 인덱스도 추가
-- (60일 윈도우 스캔용).
CREATE INDEX IF NOT EXISTS idx_appearances_entry_id ON appearances (entry_id);
CREATE INDEX IF NOT EXISTS idx_metric_snapshots_captured_at ON metric_snapshots (captured_at);
