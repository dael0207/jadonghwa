from __future__ import annotations

PROJECT = (
    "SELECT p.id, p.name, p.workspace_id, w.name AS workspace_name, p.created_at "
    "FROM projects p JOIN workspaces w ON w.id = p.workspace_id "
    "WHERE p.id = %s AND p.deleted_at IS NULL"
)
INSERT_WORKSPACE = "INSERT INTO workspaces (id, name) VALUES (%s, %s)"
INSERT_PROJECT = "INSERT INTO projects (id, workspace_id, name) VALUES (%s, %s, %s)"
INTERVIEW = (
    "SELECT i.id, i.project_id, i.status, i.active_consent, i.created_at, "
    "count(DISTINCT a.question_id)::int AS answered_count "
    "FROM interview_sessions i "
    "LEFT JOIN turns t ON t.interview_id = i.id "
    "LEFT JOIN answers a ON a.turn_id = t.id "
    "WHERE i.id = %s GROUP BY i.id"
)
PROJECT_INTERVIEWS = (
    "SELECT i.id, i.project_id, i.status, i.active_consent, i.created_at, "
    "count(DISTINCT a.question_id)::int AS answered_count "
    "FROM interview_sessions i "
    "LEFT JOIN turns t ON t.interview_id = i.id "
    "LEFT JOIN answers a ON a.turn_id = t.id "
    "WHERE i.project_id = %s GROUP BY i.id ORDER BY i.created_at ASC"
)
INSERT_INTERVIEW = (
    "INSERT INTO interview_sessions (id, project_id, status, active_consent) "
    "VALUES (%s, %s, %s, false)"
)
UPDATE_INTERVIEW_STATUS = "UPDATE interview_sessions SET status=%s, updated_at=now() WHERE id=%s"
UPDATE_INTERVIEW_CONSENTED = (
    "UPDATE interview_sessions "
    "SET status=%s, active_consent=true, updated_at=now() "
    "WHERE id=%s"
)
UPDATE_INTERVIEW_CONSENT_REVOKED = (
    "UPDATE interview_sessions "
    "SET status=%s, active_consent=false, updated_at=now() "
    "WHERE id=%s"
)
INSERT_CONSENT = (
    "INSERT INTO consent_records "
    "(id, interview_id, ai_processing, data_processing, audio_recording, retention_days) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)
REVOKE_CONSENT = (
    "UPDATE consent_records SET revoked_at=now() "
    "WHERE interview_id=%s AND revoked_at IS NULL"
)
QUESTIONS = (
    "SELECT id, stage, dimension, question_text, required, position "
    "FROM questions ORDER BY position ASC"
)
UPSERT_QUESTION = (
    "INSERT INTO questions (id, stage, dimension, question_text, position, required) "
    "VALUES (%s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (id) DO UPDATE SET "
    "stage=EXCLUDED.stage, dimension=EXCLUDED.dimension, "
    "question_text=EXCLUDED.question_text, "
    "position=EXCLUDED.position, required=EXCLUDED.required"
)
NEXT_TURN = "SELECT count(*)::int + 1 AS next_sequence FROM turns WHERE interview_id=%s"
INSERT_TURN = (
    "INSERT INTO turns (id, interview_id, sequence_number, event_type) "
    "VALUES (%s, %s, %s, %s)"
)
INSERT_ANSWER = (
    "INSERT INTO answers "
    "(id, turn_id, question_id, answer_text, answer_status, revision_of, source_refs) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)
ANSWER = (
    "SELECT a.id, a.turn_id, a.question_id, a.answer_text, a.answer_status, "
    "a.revision_of, a.source_refs, a.created_at FROM answers a WHERE a.id = %s"
)
ANSWER_IN_INTERVIEW = (
    "SELECT a.id, a.turn_id, a.question_id, a.answer_text, a.answer_status, "
    "a.revision_of, a.source_refs, a.created_at FROM answers a "
    "JOIN turns t ON t.id = a.turn_id "
    "WHERE a.id = %s AND t.interview_id = %s"
)
ANSWERS = (
    "SELECT a.id, a.turn_id, a.question_id, a.answer_text, a.answer_status, "
    "a.revision_of, a.source_refs, a.created_at FROM answers a "
    "JOIN turns t ON t.id = a.turn_id "
    "WHERE t.interview_id = %s ORDER BY t.sequence_number ASC, a.created_at ASC"
)
ANSWERED_COUNT = (
    "SELECT count(DISTINCT a.question_id)::int AS answered "
    "FROM answers a JOIN turns t ON t.id = a.turn_id WHERE t.interview_id = %s"
)
TOTAL_QUESTIONS = "SELECT count(*) AS total FROM questions"
FIRST_QUESTION_ID = "SELECT id FROM questions ORDER BY position ASC LIMIT 1"
WORK_MODEL = (
    "SELECT project_id, version, payload, schema_valid, created_at "
    "FROM work_models WHERE project_id = %s ORDER BY version DESC LIMIT 1"
)
WORK_MODEL_BY_VERSION = (
    "SELECT project_id, version, payload, schema_valid, created_at "
    "FROM work_models WHERE project_id = %s AND version = %s"
)
WORK_MODELS = (
    "SELECT project_id, version, payload, schema_valid, created_at "
    "FROM work_models WHERE project_id = %s ORDER BY version ASC"
)
WORK_MODEL_BY_ID = (
    "SELECT project_id, version, payload, schema_valid, created_at "
    "FROM work_models WHERE id = %s"
)
NEXT_MODEL_VERSION = (
    "SELECT coalesce(max(version), 0)::int + 1 AS version "
    "FROM work_models WHERE project_id = %s"
)
INSERT_WORK_MODEL = (
    "INSERT INTO work_models (id, project_id, version, payload, schema_valid) "
    "VALUES (%s, %s, %s, %s, %s)"
)
INSERT_OPPORTUNITY = (
    "INSERT INTO opportunity_drafts "
    "(id, project_id, work_model_version, payload, schema_valid) "
    "VALUES (%s, %s, %s, %s, %s)"
)
OPPORTUNITY = (
    "SELECT id, project_id, work_model_version, payload, schema_valid, created_at "
    "FROM opportunity_drafts WHERE id = %s"
)
OPPORTUNITIES_BY_PROJECT = (
    "SELECT id, project_id, work_model_version, payload, schema_valid, created_at "
    "FROM opportunity_drafts WHERE project_id = %s ORDER BY created_at ASC, id ASC"
)
INSERT_DESIGN_PACKAGE = (
    "INSERT INTO design_packages "
    "(id, project_id, opportunity_id, work_model_version, payload, schema_valid) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)
DESIGN_PACKAGE = (
    "SELECT id, project_id, opportunity_id, work_model_version, payload, schema_valid, created_at "
    "FROM design_packages WHERE id = %s"
)
DESIGN_PACKAGES_BY_PROJECT = (
    "SELECT id, project_id, opportunity_id, work_model_version, payload, schema_valid, created_at "
    "FROM design_packages WHERE project_id = %s ORDER BY created_at ASC, id ASC"
)
DESIGN_PACKAGES_BY_OPPORTUNITY = (
    "SELECT id, project_id, opportunity_id, work_model_version, payload, schema_valid, created_at "
    "FROM design_packages WHERE opportunity_id = %s ORDER BY created_at ASC, id ASC"
)
INSERT_BLUEPRINT = (
    "INSERT INTO blueprints "
    "(id, project_id, design_package_id, payload, schema_valid, export_ready) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)
BLUEPRINT = (
    "SELECT id, project_id, design_package_id, payload, schema_valid, export_ready, created_at "
    "FROM blueprints WHERE id = %s"
)
BLUEPRINTS_BY_PROJECT = (
    "SELECT id, project_id, design_package_id, payload, schema_valid, export_ready, created_at "
    "FROM blueprints WHERE project_id = %s ORDER BY created_at ASC, id ASC"
)
BLUEPRINTS_BY_DESIGN_PACKAGE = (
    "SELECT id, project_id, design_package_id, payload, schema_valid, export_ready, created_at "
    "FROM blueprints WHERE design_package_id = %s ORDER BY created_at ASC, id ASC"
)
INSERT_EVALUATION_RUN = (
    "INSERT INTO evaluation_runs (id, project_id, payload, schema_valid) "
    "VALUES (%s, %s, %s, %s)"
)
EVALUATION_RUN = (
    "SELECT id, project_id, payload, schema_valid, created_at "
    "FROM evaluation_runs WHERE id = %s"
)
EVALUATION_RUNS_BY_PROJECT = (
    "SELECT id, project_id, payload, schema_valid, created_at "
    "FROM evaluation_runs WHERE project_id = %s ORDER BY created_at ASC, id ASC"
)
INSERT_RELEASE_READINESS = (
    "INSERT INTO release_readiness_reports (id, project_id, payload, schema_valid) "
    "VALUES (%s, %s, %s, %s)"
)
RELEASE_READINESS = (
    "SELECT id, project_id, payload, schema_valid, created_at "
    "FROM release_readiness_reports WHERE id = %s"
)
RELEASE_READINESS_BY_PROJECT = (
    "SELECT id, project_id, payload, schema_valid, created_at "
    "FROM release_readiness_reports WHERE project_id = %s ORDER BY created_at ASC, id ASC"
)
INSERT_AUDIT = (
    "INSERT INTO audit_events (id, subject_id, action, metadata) "
    "VALUES (%s, %s, %s, %s) "
    "RETURNING id, subject_id, action, metadata, created_at"
)
INTERVIEW_AUDIT = (
    "SELECT id, subject_id, action, metadata, created_at FROM audit_events "
    "WHERE subject_id = %s OR metadata->>'interview_id' = %s ORDER BY created_at ASC"
)
PROJECT_AUDIT = (
    "SELECT id, subject_id, action, metadata, created_at FROM audit_events "
    "WHERE subject_id = %s OR metadata->>'project_id' = %s ORDER BY created_at ASC"
)
