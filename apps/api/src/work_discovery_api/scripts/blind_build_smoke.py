from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BlindBuildResult:
    passed: bool
    actual: dict[str, object]
    expected: dict[str, object]
    cases_executed: int


def run_blind_build(archive_path: Path) -> BlindBuildResult:
    with tempfile.TemporaryDirectory(prefix="work-discovery-blind-build-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(archive_path) as archive:
            _validate_archive_members(archive)
            archive.extractall(root)
        evidence_map = json.loads(
            (root / "traceability" / "evidence-map.json").read_text("utf-8"),
        )
        acceptance_cases = json.loads(
            (root / "tests" / "acceptance-tests.json").read_text("utf-8"),
        )
        paths_by_ref = {item["ref"]: item["target_path"] for item in evidence_map["entries"]}
        generated = root / "reference_automation.py"
        generated.write_text(_reference_automation_source(), encoding="utf-8")
        required_kinds = {"NORMAL", "ERROR", "EXCEPTION", "APPROVAL_REQUIRED"}
        observed_kinds: set[str] = set()
        normal_actual: dict[str, object] | None = None
        normal_expected: dict[str, object] | None = None
        for index, case in enumerate(acceptance_cases, 1):
            kind = str(case["kind"])
            observed_kinds.add(kind)
            input_path = _artifact_path(root, paths_by_ref[case["input_file_refs"][0]])
            expected_path = _artifact_path(root, paths_by_ref[case["expected_file_refs"][0]])
            output_path = root / f"actual-{index}.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(generated),
                    str(root / "contracts" / "mappings.json"),
                    str(input_path),
                    str(output_path),
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                process_output = completed.stderr or completed.stdout
                message = (
                    f"blind-build reference automation failed for {kind}: {process_output}"
                )
                raise RuntimeError(message)
            actual = json.loads(output_path.read_text("utf-8"))
            expected = json.loads(expected_path.read_text("utf-8"))
            if actual != expected:
                message = (
                    f"blind-build semantic mismatch for {kind}: {actual!r} != {expected!r}"
                )
                raise AssertionError(message)
            if kind == "NORMAL":
                normal_actual = actual
                normal_expected = expected
        if not required_kinds <= observed_kinds:
            missing = sorted(required_kinds - observed_kinds)
            message = f"blind-build acceptance kinds are missing: {missing}"
            raise AssertionError(message)
        if normal_actual is None or normal_expected is None:
            message = "blind-build NORMAL fixture was not executed"
            raise AssertionError(message)
        return BlindBuildResult(
            passed=True,
            actual=normal_actual,
            expected=normal_expected,
            cases_executed=len(acceptance_cases),
        )


def _validate_archive_members(archive: zipfile.ZipFile) -> None:
    for member in archive.infolist():
        path = Path(member.filename)
        file_type = (member.external_attr >> 16) & 0o170000
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in member.filename
            or file_type == 0o120000
        ):
            message = f"blind-build archive contains an unsafe member: {member.filename}"
            raise ValueError(message)


def _artifact_path(root: Path, archive_path: str) -> Path:
    candidate = (root / archive_path).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        message = f"blind-build artifact path escapes the archive: {archive_path}"
        raise ValueError(message)
    if not candidate.is_file():
        message = f"blind-build artifact is missing: {archive_path}"
        raise FileNotFoundError(message)
    return candidate


def _reference_automation_source() -> str:
    return """\
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def write_result(path: Path, result: dict[str, object]) -> None:
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )


def main() -> None:
    mappings = json.loads(Path(sys.argv[1]).read_text("utf-8"))
    with Path(sys.argv[2]).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or ())
        missing = sorted({"customer", "amount"} - headers)
        if missing:
            write_result(
                Path(sys.argv[3]),
                {
                    "error": {
                        "code": "MISSING_COLUMN",
                        "message": f"Missing required column: {missing[0]}",
                    }
                },
            )
            return
        rows = list(reader)
    for source_row, row in enumerate(rows, 2):
        try:
            amount = float(row["amount"])
        except (TypeError, ValueError):
            write_result(
                Path(sys.argv[3]),
                {
                    "error": {
                        "code": "INVALID_AMOUNT",
                        "message": f"Invalid amount at source row {source_row}",
                        "source_row": source_row,
                    }
                },
            )
            return
        if amount < 0:
            write_result(
                Path(sys.argv[3]),
                {
                    "error": {
                        "code": "INVALID_AMOUNT",
                        "message": f"Invalid amount at source row {source_row}",
                        "source_row": source_row,
                    }
                },
            )
            return
    result: dict[str, object] = {}
    for mapping in mappings:
        target = mapping["target"]
        transform = mapping["transform"]
        if transform == "COUNT(rows)":
            result[target] = len(rows)
        elif transform.startswith("SUM(DECIMAL("):
            field = transform.removeprefix("SUM(DECIMAL(").removesuffix("))")
            result[target] = sum(float(row[field]) for row in rows)
        elif " > " in transform:
            source, threshold = transform.split(" > ", 1)
            result[target] = float(result[source]) > float(threshold)
        else:
            raise ValueError(f"unsupported contract transform: {transform}")
    write_result(Path(sys.argv[3]), result)


if __name__ == "__main__":
    main()
"""


def main() -> None:
    if len(sys.argv) != 2:
        message = "usage: python -m work_discovery_api.scripts.blind_build_smoke EXPORT.zip"
        raise SystemExit(message)
    result = run_blind_build(Path(sys.argv[1]))
    print(
        json.dumps(
            {
                "passed": result.passed,
                "actual": result.actual,
                "cases_executed": result.cases_executed,
            },
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
