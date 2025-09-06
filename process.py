#!/usr/bin/env python3
# script.py — Strict-JSON preprocessor compiler (no sugar syntax)
#
# Usage:
#   python script.py preprocessor.json
#     -> writes preprocessor.compiled.json
#   python script.py preprocessor.json postprocessed.json
#
# Authoring format (strict JSON):
# {
#   "$imports": { "product": "products.json", "category": "categories.json" },
#   "product": { "$ref": "product:1" },
#   "supplier": { "$ref": "supplier:100", "$pick": { "supplier_name": "name" }, "$mode": "inline" }
# }

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from typing import Any, Dict, List, Mapping

Alias = str
IdStr = str
Index = Dict[IdStr, Any]
Indexes = Dict[Alias, Index]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def validate_alias(alias: str) -> None:
    if not ALIAS_RE.match(alias):
        raise ValueError(f"Invalid import alias '{alias}'. Use [A-Za-z][A-Za-z0-9_]*")


def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")
    except json.JSONDecodeError as ex:
        raise ValueError(f"Invalid JSON in '{path}': {ex}")


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


REF_RE = re.compile(r"""^\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$""")


def parse_ref(s: str) -> tuple[str, str]:
    """
    Parse $ref strings like 'alias:id' while ignoring any surrounding whitespace.
    Accepts: 'alias:id', 'alias:  id', ' alias :   id  '.
    Returns (alias, id) with both parts trimmed.
    """
    m = REF_RE.match(s)
    if not m:
        raise ValueError(f"Bad $ref '{s}', expected 'alias:id'")
    alias = m.group(1).strip()
    id_ = m.group(2).strip()
    validate_alias(alias)
    if not id_:
        raise ValueError(f"Bad $ref '{s}', empty id")
    return alias, id_


def make_link(obj: Mapping[str, Any]) -> Dict[str, Any]:
    # Prefer exact 'id', otherwise first '*_id'
    if "id" in obj:
        return {"id": obj["id"]}
    for k in obj.keys():
        if k.endswith("_id"):
            return {k: obj[k]}
    raise ValueError("$mode:'link' could not find an 'id' or '*_id' field")


def apply_pick(
    obj: Mapping[str, Any],
    pick: Mapping[str, str] | None,
    strict_projection: bool,
) -> Dict[str, Any]:
    if not pick:
        return dict(obj)
    out: Dict[str, Any] = {}
    for src, dst in pick.items():
        if src not in obj:
            msg = f"Projection: field '{src}' not found"
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
        if "$ref" in node and isinstance(node["$ref"], str):
            alias, id_ = parse_ref(node["$ref"])
            key = f"{alias}:{id_}"
            if key in seen_stack:
                raise ValueError(
                    f"Circular reference detected: {' -> '.join(seen_stack)} -> {key}"
                )
            if alias not in indexes:
                raise ValueError(f"Unknown alias '{alias}' in $ref '{node['$ref']}'")
            rec = indexes[alias].get(str(id_))
            if rec is None:
                raise ValueError(
                    f"Missing id '{id_}' for alias '{alias}' in $ref '{node['$ref']}'"
                )

            seen_stack.append(key)
            base = deepcopy(rec)
            picked = apply_pick(base, node.get("$pick"), strict_projection)
            resolved = make_link(picked) if node.get("$mode") == "link" else picked
            final = resolve_node(resolved, indexes, seen_stack, strict_projection)
            seen_stack.pop()
            return final

        # Regular object: recurse props
        out: Dict[str, Any] = {}
        for k, v in node.items():
            out[k] = resolve_node(v, indexes, seen_stack, strict_projection)
        return out

    # Primitives
    return node


def compile_strict(author_doc: Mapping[str, Any], base_dir: str, strict_projection: bool) -> Any:
    if not isinstance(author_doc, dict):
        raise ValueError("Root document must be a JSON object")

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
        raw = load_json(abs_path)
        indexes[alias] = index_import(alias, raw)

    # Remove $imports from the root before resolution
    author_copy = {k: v for k, v in author_doc.items() if k != "$imports"}

    return resolve_node(author_copy, indexes, seen_stack=[], strict_projection=strict_projection)


def main():
    ap = argparse.ArgumentParser(
        description="Compile a strict-JSON preprocessor file by resolving $imports and $ref."
    )
    ap.add_argument("input", help="Path to preprocessor JSON file")
    ap.add_argument(
        "output",
        nargs="?",
        help="Optional output path. If omitted, writes <input>.compiled.json",
    )
    ap.add_argument(
        "--strict-projection",
        action="store_true",
        help="Error on missing fields referenced in $pick",
    )
    ap.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent for output (default: 2)",
    )
    args = ap.parse_args()

    input_path = os.path.normpath(args.input)
    if not os.path.isfile(input_path):
        eprint(f"Input not found: {input_path}")
        sys.exit(1)

    base_dir = os.path.dirname(input_path) or "."
    try:
        author_doc = load_json(input_path)
        compiled = compile_strict(
            author_doc,
            base_dir=base_dir,
            strict_projection=args.strict_projection,
        )
    except Exception as ex:
        eprint(f"[weave error] {ex}")
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        root, ext = os.path.splitext(input_path)
        output_path = f"{root}.compiled.json"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(compiled, f, ensure_ascii=False, indent=args.indent)
            f.write("\n")
    except Exception as ex:
        eprint(f"Failed to write '{output_path}': {ex}")
        sys.exit(1)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
