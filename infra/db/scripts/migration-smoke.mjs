import { readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { PGlite } from "@electric-sql/pglite";

const requiredTables = new Set([
  "workspaces",
  "local_users",
  "projects",
  "interview_sessions",
  "consent_records",
  "turns",
  "questions",
  "answers",
  "work_models",
  "audit_events",
  "deletion_jobs",
  "question_bank_versions",
  "opportunity_drafts",
  "design_packages",
  "blueprints",
  "evaluation_runs",
  "release_readiness_reports",
  "evidence_files",
  "evidence_file_confirmations",
  "implementation_requirements",
  "implementation_packages",
]);

const requiredIndexes = new Set([
  "idx_interview_sessions_project_id",
  "idx_questions_bank_position",
  "idx_audit_events_subject_id",
  "idx_answers_revision_of",
  "idx_turns_event_type",
  "idx_opportunity_drafts_project_id",
  "idx_design_packages_project_id",
  "idx_blueprints_project_id",
  "idx_blueprints_design_package_id",
  "idx_evaluation_runs_project_id",
  "idx_release_readiness_project_id",
  "idx_evidence_files_project_created",
  "idx_evidence_file_confirmations_file_created",
  "idx_implementation_requirements_project_created",
  "idx_implementation_packages_project_created",
  "idx_implementation_packages_blueprint",
]);

const here = dirname(fileURLToPath(import.meta.url));
const migrationDir = resolve(here, "../migrations");
const migrationFiles = (await readdir(migrationDir))
  .filter((name) => name.endsWith(".sql"))
  .sort();
const db = new PGlite();

for (const file of migrationFiles) {
  const sql = await readFile(resolve(migrationDir, file), "utf8");
  await db.exec(sql);
}
const result = await db.query(
  "select tablename from pg_tables where schemaname = 'public'",
);
const created = new Set(result.rows.map((row) => row.tablename));
const missing = [...requiredTables].filter((table) => !created.has(table));

if (missing.length > 0) {
  throw new Error(`migration missing tables: ${missing.join(", ")}`);
}

const indexResult = await db.query(
  "select indexname from pg_indexes where schemaname = 'public'",
);
const indexes = new Set(indexResult.rows.map((row) => row.indexname));
const missingIndexes = [...requiredIndexes].filter((index) => !indexes.has(index));

if (missingIndexes.length > 0) {
  throw new Error(`migration missing indexes: ${missingIndexes.join(", ")}`);
}

console.log("pglite migration smoke OK");
