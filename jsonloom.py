#!
# jsonloom.py — Strict-JSON preprocessor compiler (no sugar syntax)
# Copyright 2025 Ryan Allen
# https://github.com/Hydra9268/json-loom
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Features:
# - Input preprocessor can be .json or .bson
# - $imports can point to .json or .bson (mixed allowed)
# - Output format chosen by output filename extension; if omitted, mirrors input ext
# - $ref lookups:
#     • Single ID: "alias:id" → one record
#     • Field-qualified: "alias.field:value" → array of all matches
#     • Array form: "alias.field:[v1, v2, ...]" → combined array of matches
#   (Whitespace around tokens is tolerated.)
# - $alias for projection/renaming (with optional strict mode)
# - Circular reference detection
#
# Usage:
#   python jsonloom.py preprocessor.json
#     -> writes preprocessor.compiled.json
#   python jsonloom.py preprocessor.bson
#     -> writes preprocessor.compiled.bson
#   python jsonloom.py preprocessor.json compiled.bson
#     -> writes compiled.bson
#
# Options:
#   --strict-projection   Error if $alias references missing fields (default: warn)
#   --indent N            JSON indent for output (default: 2; ignored for BSON)
#   --base64-binary       When writing JSON, convert BSON Binary values to base64 strings
#
# Notes:
# - BSON output expects a single top-level document (object), not a list; write JSON if your
#   compiled output is an array (e.g., field-qualified or array-form $ref at the root).
# - Strict projection applies to $alias only; it doesn’t affect $ref resolution.
#
# Authoring format (examples):
# {
#   "$imports": {
#     "product":  "data/products.json",
#     "category": "data/categories.json",
#     "supplier": "data/suppliers.bson"
#   },
#   "product":  { "$ref": "product: 1" },           # single ID
#   "category": { "$ref": "category :10" },         # whitespace-tolerant
#   "items":    { "$ref": "order_items.order_id: 1" },             # array (all matches)
#   "inventory":{ "$ref": "inventory.product_id: [119, 213]" },    # array of values
#   "supplier": {
#     "$ref":  "supplier:100",
#     "$alias": { "supplier_name": "name", "contact_email": "email" }
#   }
# }

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import ast
import base64
from copy import deepcopy
from typing import Any, Dict, List, Mapping

# Optional BSON support
_HAS_BSON = True
try:
    # pymongo's bson (preferred)
    from bson import BSON, decode_all, Binary as BSONBinary  # type: ignore
except Exception:
    try:
        # standalone 'bson' package fallback
        from bson import BSON, decode_all, Binary as BSONBinary  # type: ignore
    except Exception:
        _HAS_BSON = False
        BSONBinary = None  # type: ignore

Alias = str
IdStr = str
Index = Dict[IdStr, Any]
Indexes = Dict[Alias, Index]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# Whitespace-tolerant $ref like "alias:id", "alias :   id", and "alias . field : id"
REF_RE = re.compile(
    r"""^\s*([A-Za-z][A-Za-z0-9_]*)          # alias
        \s*(?:\.\s*([A-Za-z][A-Za-z0-9_]*))? # optional .field (spaces allowed)
        \s*:\s*
        (.+?)\s*$                            # value
    """, re.X
)


def lookup_record(index: Index, field: str | None, val: str) -> Mapping[str, Any] | None:
    if field is None:
        return index.get(val)  # fast path
    for rec in index.values():
        if isinstance(rec, dict) and field in rec and str(rec[field]) == val:
            return rec
    return None


def lookup_records(index: Index, field: str | None, val: str) -> List[Mapping[str, Any]]:
    """Return all matching records when a field qualifier is used; empty list if none."""
    if field is None:
        rec = index.get(val)
        return [rec] if rec is not None else []
    out: List[Mapping[str, Any]] = []
    for rec in index.values():
        if isinstance(rec, dict) and field in rec and str(rec[field]) == val:
            out.append(rec)
    return out


def validate_alias(alias: str) -> None:
    if not ALIAS_RE.match(alias):
        raise ValueError(f"Invalid import alias '{alias}'. Use [A-Za-z][A-Za-z0-9_]*")


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def load_any(path: str) -> Any:
    """Load a .json (text) or .bson (binary) file, return parsed object (dict/array)."""
    ext = _ext(path)
    if ext == ".json":
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except json.JSONDecodeError as ex:
            raise ValueError(f"Invalid JSON in '{path}': {ex}")

    elif ext == ".bson":
        if not _HAS_BSON:
            raise RuntimeError(
                f"Cannot read BSON '{path}': 'bson' package not installed. "
                f"Install via 'pip install pymongo' (or 'pip install bson')."
            )
        try:
            with open(path, "rb") as f:
                data = f.read()
            # Try to decode a single document first; if that fails, fall back to decode_all
            try:
                return BSON(data).decode()
            except Exception:
                docs = decode_all(data)
                if len(docs) == 1:
                    return docs[0]
                return docs  # list of docs
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except Exception as ex:
            raise ValueError(f"Invalid BSON in '{path}': {ex}")

    else:
        raise ValueError(f"Unsupported file extension for '{path}'. Use .json or .bson")


def _to_json_safe(obj: Any, base64_binary: bool) -> Any:
    """
    Recursively convert a Python object to something json.dump can handle.
    If base64_binary=True, BSON Binary values become base64 strings.
    Otherwise, encountering a Binary will raise a TypeError.
    """
    if _HAS_BSON and BSONBinary is not None and isinstance(obj, BSONBinary):
        if base64_binary:
            return base64.b64encode(bytes(obj)).decode("ascii")
        raise TypeError(
            "Encountered BSON Binary while writing JSON. Use --base64-binary or output .bson"
        )

    if isinstance(obj, dict):
        return {k: _to_json_safe(v, base64_binary) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v, base64_binary) for v in obj]
    return obj


def write_any(path: str, obj: Any, indent: int = 2, base64_binary: bool = False) -> None:
    """Write obj to .json (text) or .bson (binary) based on extension."""
    ext = _ext(path)
    if ext == ".json":
        safe = _to_json_safe(obj, base64_binary)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(safe, f, ensure_ascii=False, indent=indent)
            f.write("\n")
    elif ext == ".bson":
        if not _HAS_BSON:
            raise RuntimeError(
                f"Cannot write BSON '{path}': 'bson' package not installed. "
                f"Install via 'pip install pymongo' (or 'pip install bson')."
            )
        if isinstance(obj, list):
            raise ValueError(
                "BSON output expects a single document (object), but got a list. "
                "Wrap your output or export to .json instead."
            )
        with open(path, "wb") as f:
            f.write(BSON.encode(obj))
    else:
        raise ValueError(f"Unsupported output extension for '{path}'. Use .json or .bson")


def infer_id_field_from_array(arr: List[Mapping[str, Any]]) -> str | None:
    first_obj = next((x for x in arr if isinstance(x, dict)), None)
    if not first_obj:
        return None
    keys = list(first_obj.keys())
    if "id" in keys:
        return "id"
    for k in keys:
        if k.endswith("_id"):
            return k
    return None


def index_import(alias: str, raw: Any) -> Index:
    idx: Index = {}
    if isinstance(raw, list):
        id_field = infer_id_field_from_array(raw) or "id"
        for rec in raw:
            if not isinstance(rec, dict):
                raise ValueError(f"Import '{alias}': array entries must be JSON objects")
            if id_field not in rec:
                raise ValueError(f"Import '{alias}': record missing id field '{id_field}'")
            key = str(rec[id_field])
            if key in idx:
                raise ValueError(f"Import '{alias}': duplicate id '{key}'")
            idx[key] = rec
        return idx

    if isinstance(raw, dict):
        for key, rec in raw.items():
            if not isinstance(rec, dict):
                raise ValueError(
                    f"Import '{alias}': object entries must be JSON objects. Offender key='{key}'"
                )
            if key in idx:
                raise ValueError(f"Import '{alias}': duplicate id '{key}'")
            idx[str(key)] = rec
        return idx

    raise ValueError(f"Import '{alias}': must be an object or an array")


def parse_ref(s: str) -> tuple[str, str | None, str]:
    """
    Parse $ref strings like 'alias:id' while ignoring surrounding whitespace.
    Accepts: 'alias:id', 'alias:  id', ' alias :   id  '.
    Returns (alias, id) trimmed.
    """
    m = REF_RE.match(s)
    if not m:
        raise ValueError(f"Bad $ref '{s}', expected 'alias[:field]:id'")
    alias = m.group(1).strip()
    field = m.group(2).strip() if m.group(2) else None
    id_   = m.group(3).strip()
    validate_alias(alias)
    if not id_:
        raise ValueError(f"Bad $ref '{s}', empty id")
    return alias, field, id_


def apply_alias(
    obj: Mapping[str, Any],
    alias: Mapping[str, str] | None,
    strict_projection: bool,
) -> Dict[str, Any]:
    if not alias:
        return dict(obj)
    out: Dict[str, Any] = {}
    for src, dst in alias.items():
        if src not in obj:
            msg = f"Alias: field '{src}' not found"
            if strict_projection:
                raise ValueError(msg)
            eprint("[weave warning]", msg)
            continue
        out[dst] = obj[src]
    return out


def resolve_node(
    node: Any,
    indexes: Indexes,
    seen_stack: List[str],
    strict_projection: bool,
) -> Any:
    if isinstance(node, list):
        return [resolve_node(n, indexes, seen_stack, strict_projection) for n in node]

    if isinstance(node, dict):
        # $ref node?
        # $ref node?
        if "$ref" in node and isinstance(node["$ref"], str):
            alias, field, id_ = parse_ref(node["$ref"])

            # Try to parse id_ as a Python literal list
            if id_.startswith("[") and id_.endswith("]"):
                try:
                    values = ast.literal_eval(id_)
                    if not isinstance(values, list):
                        raise ValueError
                except Exception:
                    raise ValueError(f"Bad $ref array syntax: {id_}")

                results: List[Any] = []
                for v in values:
                    matches = lookup_records(indexes[alias], field, str(v))
                    if not matches:
                        raise ValueError(f"Missing record for {alias}.{field} = {v}")
                    for rec in matches:
                        base = deepcopy(rec)
                        aliased = apply_alias(base, node.get("$alias"), strict_projection)
                        results.append(resolve_node(aliased, indexes, seen_stack, strict_projection))
                return results

            # If a field qualifier is present (alias.field:id), return ALL matches as a list.
            if field is not None:
                key = f"{alias}.{field}:{id_}"
                if key in seen_stack:
                    raise ValueError(
                        f"Circular reference detected: {' -> '.join(seen_stack)} -> {key}"
                    )
                if alias not in indexes:
                    raise ValueError(f"Unknown alias '{alias}' in $ref '{node['$ref']}'")

                matches = lookup_records(indexes[alias], field, str(id_))
                if not matches:
                    raise ValueError(f"Missing record for {alias}.{field} = {id_}")

                seen_stack.append(key)
                out_list: List[Dict[str, Any]] = []
                for rec in matches:
                    base = deepcopy(rec)
                    aliased = apply_alias(base, node.get("$alias"), strict_projection)
                    resolved = resolve_node(aliased, indexes, seen_stack, strict_projection)
                    out_list.append(resolved)
                seen_stack.pop()
                return out_list

            # No field qualifier: single-record lookup by id (existing behavior)
            key = f"{alias}:{id_}"
            if key in seen_stack:
                raise ValueError(
                    f"Circular reference detected: {' -> '.join(seen_stack)} -> {key}"
                )
            if alias not in indexes:
                raise ValueError(f"Unknown alias '{alias}' in $ref '{node['$ref']}'")

            rec = lookup_record(indexes[alias], None, str(id_))
            if rec is None:
                raise ValueError(f"Missing record for {alias} = {id_}")

            seen_stack.append(key)
            base = deepcopy(rec)
            aliased = apply_alias(base, node.get("$alias"), strict_projection)
            resolved = resolve_node(aliased, indexes, seen_stack, strict_projection)
            seen_stack.pop()
            return resolved

        # Regular object: recurse
        out: Dict[str, Any] = {}
        for k, v in node.items():
            out[k] = resolve_node(v, indexes, seen_stack, strict_projection)
        return out

    # Primitives
    return node


def compile_strict(author_doc: Mapping[str, Any], base_dir: str, strict_projection: bool) -> Any:
    if not isinstance(author_doc, dict):
        raise ValueError("Root document must be a JSON/BSON object")

    imports = author_doc.get("$imports", {})
    if not isinstance(imports, dict):
        raise ValueError("$imports must be an object of { alias: path }")

    # Load and index imports relative to the author doc’s directory
    indexes: Indexes = {}
    for alias, rel_path in imports.items():
        validate_alias(alias)
        if not isinstance(rel_path, str) or not rel_path.strip():
            raise ValueError(f"$imports['{alias}'] must be a non-empty string path")
        abs_path = os.path.normpath(os.path.join(base_dir, rel_path))
        raw = load_any(abs_path)
        indexes[alias] = index_import(alias, raw)

    # Remove $imports from root before resolution
    author_copy = {k: v for k, v in author_doc.items() if k != "$imports"}

    return resolve_node(author_copy, indexes, seen_stack=[], strict_projection=strict_projection)


def main():
    ap = argparse.ArgumentParser(
        description="Compile a strict authoring file by resolving $imports and $ref (JSON/BSON)."
    )
    ap.add_argument("input", help="Path to preprocessor file (.json or .bson)")
    ap.add_argument(
        "output",
        nargs="?",
        help="Optional output path (.json or .bson). If omitted, writes <input>.compiled.<ext>",
    )
    ap.add_argument(
        "--strict-projection",
        action="store_true",
        help="Error on missing fields referenced in $alias",
    )
    ap.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent for output (default: 2; ignored for BSON)",
    )
    ap.add_argument(
        "--base64-binary",
        action="store_true",
        help="When writing JSON, convert BSON Binary values to base64 strings",
    )
    args = ap.parse_args()

    input_path = os.path.normpath(args.input)
    if not os.path.isfile(input_path):
        eprint(f"Input not found: {input_path}")
        sys.exit(1)

    base_dir = os.path.dirname(input_path) or "."
    try:
        author_doc = load_any(input_path)
        compiled = compile_strict(
            author_doc,
            base_dir=base_dir,
            strict_projection=args.strict_projection,
        )
    except Exception as ex:
        eprint(f"[loom error] {ex}")
        sys.exit(1)

    # Decide output path + extension
    if args.output:
        output_path = args.output
    else:
        root, ext = os.path.splitext(input_path)
        # mirror the input extension; default to .json if unknown
        out_ext = ext.lower() if ext.lower() in (".json", ".bson") else ".json"
        output_path = f"{root}.compiled{out_ext}"

    try:
        write_any(output_path, compiled, indent=args.indent, base64_binary=args.base64_binary)
    except Exception as ex:
        eprint(f"Failed to write '{output_path}': {ex}")
        sys.exit(1)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
