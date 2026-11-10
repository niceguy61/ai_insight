-- 리스트용 한줄 요약 (LLM 생성, 20자 내외)
ALTER TABLE entries ADD COLUMN IF NOT EXISTS summary_short_ko text;
