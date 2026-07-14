CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS local_users (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  email TEXT NOT NULL,
  display_name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS interview_sessions (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  status TEXT NOT NULL CHECK (
    status IN (
      'CREATED',
      'CONSENT_PENDING',
      'CONSENTED',
      'INTAKE_IN_PROGRESS',
      'MODEL_BUILDING',
      'PLAYBACK_CONFIRMATION',
      'OPPORTUNITY_ANALYSIS_READY',
      'FINALIZED',
      'PAUSED',
      'NEEDS_EVIDENCE',
      'CONSENT_REVOKED',
      'DELETION_PENDING',
      'ABORTED'
    )
  ),
  active_consent BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consent_records (
  id UUID PRIMARY KEY,
  interview_id UUID NOT NULL REFERENCES interview_sessions(id),
  ai_processing BOOLEAN NOT NULL,
  data_processing BOOLEAN NOT NULL,
  audio_recording BOOLEAN NOT NULL DEFAULT false,
  retention_days INTEGER NOT NULL DEFAULT 0,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,
  bank_version TEXT NOT NULL DEFAULT 'question-bank-v1',
  stage TEXT NOT NULL,
  dimension TEXT NOT NULL,
  question_text TEXT NOT NULL,
  position INTEGER NOT NULL,
  required BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS question_bank_versions (
  id TEXT PRIMARY KEY,
  source_file TEXT NOT NULL,
  seeded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS turns (
  id UUID PRIMARY KEY,
  interview_id UUID NOT NULL REFERENCES interview_sessions(id),
  sequence_number INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (interview_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS answers (
  id UUID PRIMARY KEY,
  turn_id UUID NOT NULL REFERENCES turns(id),
  question_id TEXT NOT NULL REFERENCES questions(id),
  answer_text TEXT NOT NULL,
  answer_status TEXT NOT NULL CHECK (answer_status IN ('ANSWERED', 'UNKNOWN', 'SKIPPED')),
  revision_of UUID REFERENCES answers(id),
  source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS work_models (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  version INTEGER NOT NULL,
  payload JSONB NOT NULL,
  schema_valid BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, version)
);

CREATE TABLE IF NOT EXISTS audit_events (
  id UUID PRIMARY KEY,
  subject_id UUID NOT NULL,
  action TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deletion_jobs (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  status TEXT NOT NULL,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_projects_workspace_id ON projects(workspace_id);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_project_id ON interview_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_consent_records_interview_id ON consent_records(interview_id);
CREATE INDEX IF NOT EXISTS idx_questions_bank_position ON questions(bank_version, position);
CREATE INDEX IF NOT EXISTS idx_turns_interview_id ON turns(interview_id);
CREATE INDEX IF NOT EXISTS idx_answers_turn_id ON answers(turn_id);
CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);
CREATE INDEX IF NOT EXISTS idx_work_models_project_version ON work_models(project_id, version);
CREATE INDEX IF NOT EXISTS idx_audit_events_subject_id ON audit_events(subject_id);
CREATE INDEX IF NOT EXISTS idx_deletion_jobs_project_id ON deletion_jobs(project_id);

INSERT INTO question_bank_versions (id, source_file)
VALUES ('question-bank-v1', 'question-bank-v1.json')
ON CONFLICT (id) DO NOTHING;
