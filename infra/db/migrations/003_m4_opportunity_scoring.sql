CREATE INDEX IF NOT EXISTS idx_opportunity_drafts_project_created_at
  ON opportunity_drafts(project_id, created_at);

CREATE INDEX IF NOT EXISTS idx_opportunity_drafts_project_version
  ON opportunity_drafts(project_id, work_model_version);

CREATE INDEX IF NOT EXISTS idx_opportunity_drafts_schema_valid
  ON opportunity_drafts(schema_valid);
