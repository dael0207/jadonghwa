CREATE INDEX IF NOT EXISTS idx_answers_revision_of ON answers(revision_of);
CREATE INDEX IF NOT EXISTS idx_turns_event_type ON turns(event_type);

CREATE TABLE IF NOT EXISTS opportunity_drafts (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  work_model_version INTEGER NOT NULL,
  payload JSONB NOT NULL,
  schema_valid BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (project_id, work_model_version) REFERENCES work_models(project_id, version)
);

CREATE INDEX IF NOT EXISTS idx_opportunity_drafts_project_id ON opportunity_drafts(project_id);
