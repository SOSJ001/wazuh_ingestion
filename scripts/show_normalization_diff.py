#!/usr/bin/env python3
"""
Show raw Wazuh alert JSON vs normalized record for dissertation Figure 4.

Usage examples:
  python scripts/show_normalization_diff.py --raw-file sample_alert.json
  python scripts/show_normalization_diff.py --from-indexer
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_repo_on_path() -> None:
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _load_env() -> None:
    if load_dotenv:
        load_dotenv(_repo_root() / ".env")


def _extract_raw_alert(payload: Any) -> dict[str, Any]:
    """
    Accept one of:
    - raw alert dict (with id/@timestamp/agent/rule)
    - list[raw alert]
    - OpenSearch _search response (hits.hits[]._source)
    """
    if isinstance(payload, dict):
        hits = payload.get("hits")
        if isinstance(hits, dict):
            inner_hits = hits.get("hits")
            if isinstance(inner_hits, list) and inner_hits:
                first = inner_hits[0]
                if isinstance(first, dict):
                    src = first.get("_source")
                    if isinstance(src, dict):
                        return src
        if "_source" in payload and isinstance(payload.get("_source"), dict):
            return payload["_source"]
        return payload

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict) and isinstance(first.get("_source"), dict):
            return first["_source"]
        if isinstance(first, dict):
            return first

    raise ValueError("Could not extract a raw alert object from the supplied input.")


def _normalized_tuple_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    keys = [
        "id",
        "timestamp",
        "agent_name",
        "agent_id",
        "rule_level",
        "rule_description",
        "rule_id",
        "full_log",
        "log_hmac",
        "hmac_algo",
        "hmac_created_at",
    ]
    return dict(zip(keys, row))


def _load_raw_from_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = _extract_raw_alert(payload)
    if not isinstance(raw, dict):
        raise ValueError("Parsed input is not a JSON object.")
    return raw


def _fetch_raw_from_indexer() -> dict[str, Any]:
    _ensure_repo_on_path()
    # Import lazily so env vars are loaded first.
    import wazuh_ingestion as wi

    auth = (wi.INDEXER_USER, wi.INDEXER_PASS)
    ok, alerts = asyncio.run(wi._tunnel_and_fetch(auth))
    if not ok or not alerts:
        raise RuntimeError("No alerts returned from indexer tunnel fetch.")
    raw = alerts[0]
    if not isinstance(raw, dict):
        raise RuntimeError("Unexpected alert payload shape from indexer.")
    return raw


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    _ensure_repo_on_path()
    import wazuh_ingestion as wi

    row = wi._normalize_alert(raw)
    if row is None:
        raise RuntimeError("Normalization returned None (missing alert id).")
    return _normalized_tuple_to_dict(row)


def _mapping_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "raw.id",
        "timestamp": "raw.@timestamp (fallback raw.timestamp)",
        "agent_name": "raw.agent.name",
        "agent_id": "raw.agent.id",
        "rule_level": "raw.rule.level (int, default 0)",
        "rule_description": "raw.rule.description",
        "rule_id": "raw.rule.id (as string)",
        "full_log": "raw.full_log | raw.data | raw.data.log | raw.data.message | raw.message | raw.log",
        "log_hmac": "HMAC-SHA256(full_log, ALERT_HMAC_SECRET)",
        "hmac_algo": "constant: HMAC-SHA256",
        "hmac_created_at": "UTC timestamp at normalization time",
        "raw_has_full_log": "yes" if isinstance(raw.get("full_log"), str) and raw.get("full_log") else "no",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a screenshot-friendly raw-vs-normalized alert comparison."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--raw-file",
        help="Path to JSON input file (raw alert, list, or _search response).",
    )
    source.add_argument(
        "--from-indexer",
        action="store_true",
        help="Fetch one latest alert from indexer via the same SSH tunnel flow.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to save combined comparison JSON output.",
    )
    args = parser.parse_args()

    _load_env()

    try:
        if args.raw_file:
            raw = _load_raw_from_file(Path(args.raw_file))
            source_label = f"file: {args.raw_file}"
        else:
            raw = _fetch_raw_from_indexer()
            source_label = "live indexer fetch via SSH tunnel"

        normalized = _normalize(raw)
        mapping = _mapping_summary(raw)

        print("=" * 88)
        print("FIGURE 4 - JSON TO RELATIONAL NORMALIZATION")
        print(f"Source: {source_label}")
        print("=" * 88)
        print("\n[RAW ALERT JSON]")
        print(json.dumps(raw, indent=2, ensure_ascii=False))
        print("\n" + "-" * 88)
        print("[NORMALIZED RECORD (alerts table shape)]")
        print(json.dumps(normalized, indent=2, ensure_ascii=False))
        print("\n" + "-" * 88)
        print("[FIELD MAPPING SUMMARY]")
        print(json.dumps(mapping, indent=2, ensure_ascii=False))
        print("\nNote: hmac_created_at and log_hmac are generated at normalization time.")

        if args.output_json:
            combined = {
                "source": source_label,
                "raw_alert": raw,
                "normalized_record": normalized,
                "field_mapping": mapping,
            }
            Path(args.output_json).write_text(
                json.dumps(combined, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Saved comparison JSON: {args.output_json}")

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
