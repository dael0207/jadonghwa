from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath

from defusedxml import ElementTree

from work_discovery_api.models import EvidenceFileUpload, JsonObject, JsonValue

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_SAMPLE_ROWS = 20
SUPPORTED_CONTENT_TYPES: dict[str, frozenset[str]] = {
    ".csv": frozenset({"text/csv", "application/csv", "text/plain"}),
    ".json": frozenset({"application/json", "text/json", "text/plain"}),
    ".xlsx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream",
        },
    ),
}
SENSITIVE_FIELD_PATTERN = re.compile(
    r"(?:^|[_-])(password|passwd|secret|token|api[_-]?key|credential|private[_-]?key)(?:$|[_-])",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"(?im)^[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)[A-Z0-9_]*"
    r"\s*=\s*[^\s#][^\r\n]*$",
)
ABSOLUTE_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:[\\/]")
ABSOLUTE_UNIX_PATH = re.compile(r"(?<![\w.])/(?:Users|home|root|tmp|var|etc|opt)/")


class EvidenceFileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExtractedEvidence:
    filename: str
    content_type: str
    content: bytes
    sha256: str
    extracted_schema: JsonObject
    sample_values: JsonObject


def decode_and_extract(upload: EvidenceFileUpload) -> ExtractedEvidence:
    filename = _safe_filename(upload.filename)
    extension = PurePath(filename).suffix.lower()
    allowed_types = SUPPORTED_CONTENT_TYPES.get(extension)
    if allowed_types is None or upload.content_type.lower() not in allowed_types:
        message = "only CSV, JSON, and XLSX evidence files are supported"
        raise EvidenceFileError(message)
    try:
        content = base64.b64decode(upload.content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        message = "content_base64 is not valid base64"
        raise EvidenceFileError(message) from error
    if not content:
        message = "evidence file must not be empty"
        raise EvidenceFileError(message)
    if len(content) > MAX_FILE_BYTES:
        message = "evidence file exceeds the 5 MiB limit"
        raise EvidenceFileError(message)

    if extension == ".csv":
        extracted_schema, sample_values = _extract_csv(content)
    elif extension == ".json":
        extracted_schema, sample_values = _extract_json(content)
    else:
        extracted_schema, sample_values = _extract_xlsx(content)
    _reject_sensitive_fields(extracted_schema)
    return ExtractedEvidence(
        filename=filename,
        content_type=upload.content_type.lower(),
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        extracted_schema=extracted_schema,
        sample_values=sample_values,
    )


def _safe_filename(filename: str) -> str:
    normalized = filename.strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or "/" in normalized
        or "\\" in normalized
        or PurePath(normalized).name != normalized
    ):
        message = "filename must be a plain relative filename"
        raise EvidenceFileError(message)
    return normalized


def _extract_csv(content: bytes) -> tuple[JsonObject, JsonObject]:
    text = _decode_utf8(content)
    _reject_unsafe_text(text)
    reader = csv.DictReader(io.StringIO(text))
    headers = tuple(header.strip() for header in (reader.fieldnames or ()) if header.strip())
    if not headers:
        message = "CSV must include a non-empty header row"
        raise EvidenceFileError(message)
    if len(set(headers)) != len(headers):
        message = "CSV headers must be unique"
        raise EvidenceFileError(message)
    rows = [dict(row) for _, row in zip(range(MAX_SAMPLE_ROWS), reader, strict=False)]
    properties = {
        header: _column_schema([str(row.get(header, "")) for row in rows]) for header in headers
    }
    schema: JsonObject = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(headers),
            "properties": properties,
        },
    }
    samples: JsonObject = {
        "format": "CSV",
        "row_count_sampled": len(rows),
        "rows": rows[:5],
    }
    return schema, samples


def _extract_json(content: bytes) -> tuple[JsonObject, JsonObject]:
    text = _decode_utf8(content)
    _reject_unsafe_text(text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        message = f"invalid JSON: {error.msg}"
        raise EvidenceFileError(message) from error
    if not isinstance(value, dict | list):
        message = "JSON evidence must contain an object or array"
        raise EvidenceFileError(message)
    schema = _schema_for_value(value)
    sample_value: JsonValue = value[:5] if isinstance(value, list) else value
    return schema, {"format": "JSON", "value": sample_value}


def _extract_xlsx(content: bytes) -> tuple[JsonObject, JsonObject]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as workbook:
            infos = workbook.infolist()
            if sum(info.file_size for info in infos) > MAX_XLSX_UNCOMPRESSED_BYTES:
                message = "XLSX uncompressed content exceeds the safety limit"
                raise EvidenceFileError(message)
            if any(_unsafe_archive_member(info.filename) for info in infos):
                message = "XLSX contains an unsafe archive path"
                raise EvidenceFileError(message)
            names = {info.filename for info in infos}
            sheet_name = "xl/worksheets/sheet1.xml"
            if sheet_name not in names:
                message = "XLSX must contain a first worksheet"
                raise EvidenceFileError(message)
            shared = _xlsx_shared_strings(workbook, names)
            rows = _xlsx_rows(workbook.read(sheet_name), shared)
    except zipfile.BadZipFile as error:
        message = "invalid XLSX archive"
        raise EvidenceFileError(message) from error
    if not rows:
        message = "XLSX first worksheet must contain a header row"
        raise EvidenceFileError(message)
    _reject_unsafe_values(rows)
    headers = tuple(str(value).strip() for value in rows[0] if str(value).strip())
    if not headers or len(set(headers)) != len(headers):
        message = "XLSX headers must be non-empty and unique"
        raise EvidenceFileError(message)
    data_rows = [
        {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        for row in rows[1 : MAX_SAMPLE_ROWS + 1]
    ]
    properties = {
        header: _column_schema([str(row.get(header, "")) for row in data_rows])
        for header in headers
    }
    schema: JsonObject = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": list(headers),
            "properties": properties,
        },
    }
    return schema, {
        "format": "XLSX",
        "row_count_sampled": len(data_rows),
        "rows": data_rows[:5],
    }


def _decode_utf8(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        message = "text evidence must be UTF-8 encoded"
        raise EvidenceFileError(message) from error


def _column_schema(values: list[str]) -> JsonObject:
    non_empty = [value.strip() for value in values if value.strip()]
    if non_empty and all(value.lower() in {"true", "false"} for value in non_empty):
        return {"type": "boolean"}
    if non_empty and all(re.fullmatch(r"-?\d+", value) for value in non_empty):
        return {"type": "integer"}
    if non_empty and all(_is_number(value) for value in non_empty):
        return {"type": "number"}
    return {"type": "string"}


def _is_number(value: str) -> bool:
    try:
        _ = float(value)
    except ValueError:
        return False
    return True


def _schema_for_value(value: JsonValue) -> JsonObject:
    if isinstance(value, dict):
        properties = {str(key): _schema_for_value(item) for key, item in value.items()}
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        }
    if isinstance(value, list):
        item_schema = _schema_for_value(value[0]) if value else {}
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "array",
            "items": item_schema,
        }
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if value is None:
        return {"type": "null"}
    return {"type": "string"}


def _reject_sensitive_fields(schema: JsonObject) -> None:
    properties = schema.get("properties")
    sensitive: list[str] = []
    if isinstance(properties, dict):
        for name, child in properties.items():
            if SENSITIVE_FIELD_PATTERN.search(str(name)):
                sensitive.append(str(name))
            if isinstance(child, dict):
                try:
                    _reject_sensitive_fields(dict(child))
                except EvidenceFileError as error:
                    sensitive.append(str(error))
    items = schema.get("items")
    if isinstance(items, dict):
        try:
            _reject_sensitive_fields(dict(items))
        except EvidenceFileError as error:
            sensitive.append(str(error))
    if sensitive:
        message = f"evidence contains secret-like fields that cannot be exported: {sensitive}"
        raise EvidenceFileError(message)


def _reject_unsafe_text(text: str) -> None:
    if ABSOLUTE_WINDOWS_PATH.search(text) or ABSOLUTE_UNIX_PATH.search(text):
        message = "evidence contains an absolute filesystem path"
        raise EvidenceFileError(message)
    if SECRET_VALUE_PATTERN.search(text):
        message = "evidence contains a secret-like assignment"
        raise EvidenceFileError(message)


def _reject_unsafe_values(value: object) -> None:
    if isinstance(value, str):
        _reject_unsafe_text(value)
    elif isinstance(value, dict):
        for child in value.values():
            _reject_unsafe_values(child)
    elif isinstance(value, list | tuple):
        for child in value:
            _reject_unsafe_values(child)


def _unsafe_archive_member(name: str) -> bool:
    path = PurePosixPath(name)
    return path.is_absolute() or ".." in path.parts or "\\" in name


def _xlsx_shared_strings(
    workbook: zipfile.ZipFile,
    names: set[str],
) -> tuple[str, ...]:
    name = "xl/sharedStrings.xml"
    if name not in names:
        return ()
    root = ElementTree.fromstring(workbook.read(name))
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    return tuple(
        "".join(node.text or "" for node in item.iter(f"{namespace}t"))
        for item in root.iter(f"{namespace}si")
    )


def _xlsx_rows(sheet_xml: bytes, shared: tuple[str, ...]) -> list[list[str]]:
    root = ElementTree.fromstring(sheet_xml)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    result: list[list[str]] = []
    for row in root.iter(f"{namespace}row"):
        values: list[str] = []
        for cell in row.iter(f"{namespace}c"):
            value_node = cell.find(f"{namespace}v")
            value = value_node.text if value_node is not None and value_node.text else ""
            if cell.attrib.get("t") == "s" and value:
                index = int(value)
                value = shared[index] if index < len(shared) else ""
            elif cell.attrib.get("t") == "inlineStr":
                value = "".join(node.text or "" for node in cell.iter(f"{namespace}t"))
            values.append(value)
        result.append(values)
    return result
