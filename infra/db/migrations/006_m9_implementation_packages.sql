CREATE TABLE IF NOT EXISTS evidence_files (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    role TEXT NOT NULL CHECK (role IN ('INPUT', 'EXPECTED_OUTPUT')),
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    content BYTEA NOT NULL,
    extracted_schema JSONB NOT NULL,
    sample_values JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence_file_confirmations (
    id UUID PRIMARY KEY,
    evidence_file_id UUID NOT NULL REFERENCES evidence_files(id),
    confirmed BOOLEAN NOT NULL,
    confirmed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS implementation_requirements (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    payload JSONB NOT NULL,
    confirmed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS implementation_packages (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    blueprint_id UUID NOT NULL REFERENCES blueprints(id),
    payload JSONB NOT NULL,
    schema_valid BOOLEAN NOT NULL DEFAULT false,
    readiness_status TEXT NOT NULL CHECK (
        readiness_status IN ('DESIGN_READY', 'IMPLEMENTATION_READY', 'CODEGEN_READY')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_files_project_created
    ON evidence_files(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_file_confirmations_file_created
    ON evidence_file_confirmations(evidence_file_id, created_at);
CREATE INDEX IF NOT EXISTS idx_implementation_requirements_project_created
    ON implementation_requirements(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_implementation_packages_project_created
    ON implementation_packages(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_implementation_packages_blueprint
    ON implementation_packages(blueprint_id);
