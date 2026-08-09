#!/usr/bin/env python3
"""
Generate src/frontend/api/types.gen.ts from the FastAPI OpenAPI 3.1 schema.

DEC-02 makes the generated schema the contract SSOT, and issue #91 requires the frontend
types be generated from it rather than hand-maintained — `appStore.ts` already carried a
parallel `WorkspaceItem`/`FileItem` definition, which is exactly the drift this prevents.

Why a Python script instead of `openapi-typescript`:
  - Zero new dependencies. DEC-01 allows Node only as a build-time toolchain for the React
    bundle; adding an npm devDependency whose output is committed source widens that surface
    for no gain here.
  - The output is checked by pytest (tests/test_ws_fe_01.py regenerates it in memory and
    compares), so the generated file cannot silently drift from the schema. With no test
    runner on the frontend side, that pytest check is the only enforcement available.

Emitted shape:
  - one `export interface` per `components.schemas` entry, named verbatim so the mapping
    back to the schema is 1:1 (FastAPI's names — `ApiResponse_FileListRes_` — are already
    valid TS identifiers)
  - `snake_case` property names, untouched. DEC-03 forbids a camelCase conversion layer at
    every layer, and that includes this generator: a rename here would be exactly the alias
    drift the rule exists to stop.
  - `API_PATHS`, the route table, so a typo'd URL in the client is a compile error

Usage:
    python scripts/gen_api_types.py            # write the file
    python scripts/gen_api_types.py --check    # exit 1 if the file is stale (no write)
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_PATH = REPO_ROOT / "src" / "frontend" / "api" / "types.gen.ts"

HEADER = """/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by `python scripts/gen_api_types.py` from the FastAPI OpenAPI 3.1 schema, which
 * DEC-02 designates as the IPC contract SSOT. Editing this file by hand recreates the
 * hand-maintained parallel type definition that issue #91 removed.
 *
 * Property names are `snake_case` exactly as they appear on the wire (DEC-03) — there is no
 * camelCase conversion layer anywhere, this file included.
 *
 * To change a type: change the Pydantic DTO in src/backend/api/dtos.py, then regenerate.
 * tests/test_ws_fe_01.py fails if this file and the live schema disagree.
 */
"""


def build_openapi_schema() -> Dict[str, Any]:
    """
    Build the app against a throwaway SQLite file and return its OpenAPI schema.

    A temp DB rather than the real one at %LocalAppData%: generating types must not create or
    migrate a user's database as a side effect.
    """
    from src.backend.api.app import create_app
    from src.backend.db import DatabaseManager

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(
            db_path=os.path.join(tmpdir, "schema_gen.db"),
            migrations_dir=str(REPO_ROOT / "migrations"),
        )
        try:
            app = create_app(db_mgr, session_token="schema-generation-only")
            return app.openapi()
        finally:
            db_mgr.close()


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def ts_type(schema: Optional[Dict[str, Any]]) -> str:
    """
    Map one JSON-Schema node onto a TypeScript type.

    Covers only the constructs Pydantic v2 actually emits for these DTOs — `$ref`, `anyOf`
    (which is how `Optional[X]` is expressed in OpenAPI 3.1), arrays, and the five scalar
    types. Anything unrecognised becomes `unknown` rather than `any`, so an unhandled
    construct surfaces as a type error at the call site instead of silently disabling
    checking there.
    """
    if not schema:
        return "unknown"

    if "$ref" in schema:
        return _ref_name(schema["$ref"])

    if "anyOf" in schema:
        parts = [ts_type(sub) for sub in schema["anyOf"]]
        # Deduplicate while keeping order: anyOf[str, null] twice over would read as
        # `string | null | string | null`.
        seen: List[str] = []
        for part in parts:
            if part not in seen:
                seen.append(part)
        return " | ".join(seen)

    if "allOf" in schema:
        return " & ".join(ts_type(sub) for sub in schema["allOf"])

    schema_type = schema.get("type")
    if schema_type == "array":
        inner = ts_type(schema.get("items"))
        # Parenthesise unions so `A | B[]` cannot be read as `A | (B[])`.
        return f"({inner})[]" if "|" in inner else f"{inner}[]"
    if schema_type == "object":
        # A bare object with no properties is Dict[str, Any] — e.g. TaskResultRes.result,
        # whose contents vary per task type and are therefore not part of the contract.
        return "Record<string, unknown>"
    if schema_type == "string":
        return "string"
    if schema_type in ("integer", "number"):
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    return "unknown"


def _doc_comment(text: str, indent: str) -> List[str]:
    """Render a schema description as a JSDoc block, preserving its line breaks."""
    lines = [line.rstrip() for line in text.strip().splitlines()]
    out = [f"{indent}/**"]
    out.extend(f"{indent} * {line}".rstrip() for line in lines)
    out.append(f"{indent} */")
    return out


def render_interface(name: str, schema: Dict[str, Any]) -> str:
    lines: List[str] = []
    if schema.get("description"):
        lines.extend(_doc_comment(schema["description"], ""))
    lines.append(f"export interface {name} {{")

    properties: Dict[str, Any] = schema.get("properties") or {}
    required = set(schema.get("required") or [])

    if not properties:
        lines.append("  [key: string]: unknown;")

    for prop_name, prop_schema in properties.items():
        if prop_schema.get("description"):
            lines.extend(_doc_comment(prop_schema["description"], "  "))
        rendered = ts_type(prop_schema)
        # A field with a default is present in every response but may be omitted from a
        # request body, so it is optional on the TS side. Required-and-nullable stays
        # required: the key is always there, its value may be null.
        optional = prop_name not in required
        marker = "?" if optional else ""
        lines.append(f"  {prop_name}{marker}: {rendered};")

    lines.append("}")
    return "\n".join(lines)


def _path_key(method: str, path: str) -> str:
    """
    Derive a stable API_PATHS key from the method and path.

    Not FastAPI's `operationId`: that is `func_name__path_method`, so renaming a route handler
    would rename the frontend's key and break the client for no contract reason. Method + path
    changes only when the contract itself does.

    `POST /api/v1/workspace/{workspace_id}/rename/diff` -> `POST_workspace_rename_diff`
    `GET  /api/v1/workspace`                            -> `GET_workspace`
    `GET  /api/v1/workspace/{workspace_id}`             -> `GET_workspace_item`

    Path parameters are dropped from the middle of a path because they add nothing a reader
    needs. A path that *ends* in one gets `_item` instead: without it the collection route and
    the single-resource route collapse onto the same key, which is a duplicate property in the
    emitted object literal.
    """
    raw_segments = path.strip("/").split("/")
    segments: List[str] = []
    for segment in raw_segments:
        if segment in ("api", "v1") or (segment.startswith("{") and segment.endswith("}")):
            continue
        segments.append(segment)
    last = raw_segments[-1]
    if last.startswith("{") and last.endswith("}"):
        segments.append("item")
    key = f"{method.upper()}_{'_'.join(segments)}"
    # A hyphen in a path segment (`/watcher/idle-flush`) is legal in a URL but not in a
    # TypeScript identifier, so the emitted object literal failed to parse — `tsc` reported
    # `TS1005: ',' expected` in a GENERATED file, which reads as a generator bug rather than a
    # routing choice and sends the reader to the wrong place. Normalising here means any future
    # hyphenated route just works.
    return re.sub(r"[^A-Za-z0-9_]", "_", key)


def render_paths(schema: Dict[str, Any]) -> str:
    """
    Emit the route table as a frozen const.

    A typo'd URL in the client would otherwise be a 404 discovered by clicking, and the token
    middleware answers an unrouted /api/v1 path with UNAUTHORIZED — a misleading symptom. With
    this table the typo does not compile.
    """
    entries: List[str] = []
    seen_keys: Dict[str, str] = {}
    for path, operations in sorted(schema.get("paths", {}).items()):
        for method in sorted(operations):
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            key = _path_key(method, path)
            # A duplicate key is TS1117 in an object literal, i.e. a build break, and the
            # second entry would silently win at runtime. Fail here instead: a new route that
            # collides needs _path_key extended, not a broken client.
            if key in seen_keys:
                raise ValueError(
                    f"duplicate API_PATHS key {key!r}: "
                    f"{seen_keys[key]} and {method.upper()} {path} collide"
                )
            seen_keys[key] = f"{method.upper()} {path}"
            entries.append(f"  {key}: {json.dumps(path)},")
    body = "\n".join(entries)
    return (
        "/**\n"
        " * Every registered route, keyed by METHOD_resource.\n"
        " *\n"
        " * Path parameters are left as `{workspace_id}` placeholders — the client substitutes\n"
        " * them, so the literal here stays identical to what OpenAPI declares.\n"
        " */\n"
        f"export const API_PATHS = {{\n{body}\n}} as const;"
    )


def generate(schema: Dict[str, Any]) -> str:
    schemas: Dict[str, Any] = schema.get("components", {}).get("schemas", {})
    blocks = [HEADER.rstrip()]
    for name in sorted(schemas):
        blocks.append(render_interface(name, schemas[name]))
    blocks.append(render_paths(schema))
    # Trailing newline so the file is POSIX-clean and git does not report "no newline at EOF".
    return "\n\n".join(blocks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed file matches the live schema; write nothing",
    )
    args = parser.parse_args()

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    generated = generate(build_openapi_schema())

    if args.check:
        if not OUTPUT_PATH.is_file():
            print(f"[gen_api_types] MISSING: {OUTPUT_PATH.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1
        # read_text is universal-newlines, so a core.autocrlf checkout (CRLF on disk) still
        # compares equal to the LF we generate. Do not switch this to read_bytes.
        current = OUTPUT_PATH.read_text(encoding="utf-8")
        if current != generated:
            print(
                "[gen_api_types] STALE: types.gen.ts does not match the OpenAPI schema.\n"
                "  Run: python scripts/gen_api_types.py",
                file=sys.stderr,
            )
            return 1
        print("[gen_api_types] up to date.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" so the committed file is LF on Windows too and --check does not fail on
    # line endings alone.
    OUTPUT_PATH.write_text(generated, encoding="utf-8", newline="\n")
    interface_count = generated.count("export interface ")
    print(f"[gen_api_types] wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({interface_count} interfaces)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
