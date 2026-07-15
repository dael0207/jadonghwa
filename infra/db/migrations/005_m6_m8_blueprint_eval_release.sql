CREATE TABLE IF NOT EXISTS blueprints (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  design_package_id UUID NOT NULL REFERENCES design_packages(id),
  payload JSONB NOT NULL,
  schema_valid BOOLEAN NOT NULL DEFAULT false,
  export_ready BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  payload JSONB NOT NULL,
  schema_valid BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS release_readiness_reports (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  payload JSONB NOT NULL,
  schema_valid BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_blueprints_project_id
  ON blueprints(project_id);

CREATE INDEX IF NOT EXISTS idx_blueprints_design_package_id
  ON blueprints(design_package_id);

CREATE INDEX IF NOT EXISTS idx_blueprints_created_at
  ON blueprints(created_at);

CREATE INDEX IF NOT EXISTS idx_blueprints_project_created_at
  ON blueprints(project_id, created_at);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_project_id
  ON evaluation_runs(project_id);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_created_at
  ON evaluation_runs(created_at);

CREATE INDEX IF NOT EXISTS idx_release_readiness_project_id
  ON release_readiness_reports(project_id);

CREATE INDEX IF NOT EXISTS idx_release_readiness_created_at
  ON release_readiness_reports(created_at);
