import { readFile } from "node:fs/promises";
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
]);

const here = dirname(fileURLToPath(import.meta.url));
const migrationPath = resolve(here, "../migrations/001_m0_foundation.sql");
const sql = await readFile(migrationPath, "utf8");
const db = new PGlite();

await db.exec(sql);
const result = await db.query(
  "select tablename from pg_tables where schemaname = 'public'",
);
const created = new Set(result.rows.map((row) => row.tablename));
const missing = [...requiredTables].filter((table) => !created.has(table));

if (missing.length > 0) {
  throw new Error(`migration missing tables: ${missing.join(", ")}`);
}

console.log("pglite migration smoke OK");
