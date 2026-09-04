import csv
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from src.storage import sha256_file

RETRIEVAL_COLS = [
    "unit_id", "source", "source_url_or_query", "subreddit", "start_ts", "end_ts",
    "content_type", "status", "attempt_count", "started_at", "completed_at", "last_cursor",
    "n_read", "n_usable", "token_estimate", "output_tmp", "output_final", "output_sha256",
    "error_category", "error_excerpt", "config_version", "config_sha256", "retrieval_date"
]

SHARD_COLS = [
    "shard_id", "corpus", "subreddit", "period_id", "content_type", "n_records",
    "n_tokens", "min_ts", "max_ts", "path", "sha256", "bytes_compressed",
    "source_unit_ids", "status", "config_version", "config_sha256", "created_at"
]

TRAINING_COLS = [
    "model_id", "corpus_type", "subreddit_or_group", "period_id", "spec_hash",
    "dim", "window", "sg", "negative", "epochs", "min_count", "max_vocab",
    "subsample", "workers", "lr", "seed", "vocab_size", "words_processed",
    "epochs_done", "train_secs", "peak_ram_mb", "model_path", "vectors_path",
    "model_sha256", "vectors_sha256", "config_version", "status", "diagnostics_path"
]


def load_manifest(path: Union[str, Path]) -> List[Dict[str, str]]:
    """Load manifest CSV as list of dicts, returning empty list if not existing."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    with open(p, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if not (r.get(list(r.keys())[0], "") or "").startswith("#")]


def upsert_manifest_row(
    path: Union[str, Path],
    row: dict,
    key_fields: List[str],
    all_fields: List[str]
) -> None:
    """Atomically upsert a row into a manifest CSV matching on key_fields."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = load_manifest(p)
    
    def matches_key(r: dict) -> bool:
        return all(str(r.get(k, "")) == str(row.get(k, "")) for k in key_fields)
        
    filtered = [r for r in existing if not matches_key(r)]
    # Ensure all row values are present and formatted
    clean_row = {k: str(row.get(k, "")) for k in all_fields}
    filtered.append(clean_row)
    
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_fields)
        w.writeheader()
        w.writerows(filtered)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def verify_output_shards(output_paths_str: str, expected_sha_str: str) -> bool:
    """Verify that all shard files exist, are non-empty, and match recorded checksum(s).
    
    Handles both single paths and semicolon-delimited lists of paths.
    Addresses both exact raw SHA and combined SHA formats.
    """
    if not output_paths_str or not output_paths_str.strip():
        return False
        
    paths = [Path(p.strip()) for p in output_paths_str.split(";") if p.strip()]
    if not paths:
        return False
        
    for p in paths:
        if not p.exists() or p.stat().st_size == 0:
            return False
            
    # Compute actual hashes
    actual_shas = [sha256_file(p) for p in paths]
    expected_tokens = [s.strip() for s in expected_sha_str.split(";") if s.strip()]
    
    # 1. Exact match per file
    if actual_shas == expected_tokens:
        return True
        
    # 2. Combined single hash match: sha256(";".join(actual_shas))
    combined_hash = hashlib.sha256(";".join(actual_shas).encode()).hexdigest()
    if combined_hash == expected_sha_str.strip():
        return True
        
    # 3. Single file direct match
    if len(actual_shas) == 1 and actual_shas[0] == expected_sha_str.strip():
        return True
        
    return False
