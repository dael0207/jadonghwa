CREATE TABLE IF NOT EXISTS design_packages (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  opportunity_id UUID NOT NULL REFERENCES opportunity_drafts(id),
  work_model_version INTEGER NOT NULL,
  payload JSONB NOT NULL,
  schema_valid BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (project_id, work_model_version)
    REFERENCES work_models(project_id, version)
);

CREATE INDEX IF NOT EXISTS idx_design_packages_project_id
  ON design_packages(project_id);

CREATE INDEX IF NOT EXISTS idx_design_packages_opportunity_id
  ON design_packages(opportunity_id);

CREATE INDEX IF NOT EXISTS idx_design_packages_created_at
  ON design_packages(created_at);

CREATE INDEX IF NOT EXISTS idx_design_packages_project_created_at
  ON design_packages(project_id, created_at);
