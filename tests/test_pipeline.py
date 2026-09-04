import hashlib
import os
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.paths as paths
import src.storage as storage
import src.cleaner as cleaner
import src.manifests as manifests


def test_paths():
    print("Testing src.paths...")
    root = paths.get_project_root()
    assert (root / "config/project_config.yaml").exists(), "Config not found at root"
    tmp = paths.resolve_tmp(root)
    assert tmp.exists(), "Tmp directory was not created"
    print("  paths: PASS")


def test_cleaner():
    print("Testing src.cleaner...")
    # Negation retention
    toks, info = cleaner.clean_and_tokenize("This is NOT a bad example, never broken.")
    assert "not" in toks, "'not' must be retained"
    assert "never" in toks, "'never' must be retained"
    assert info["dropped"] is None

    # Redactions and tokens
    toks, info = cleaner.clean_and_tokenize("Check https://example.com/test and u/some_user on r/academia!")
    assert "<url>" in toks
    assert "<user>" in toks
    assert "<subreddit>" in toks

    # Emoji and code
    toks, info = cleaner.clean_and_tokenize("Code block: ```python print(1)``` with emoji 🎓🎉")
    assert "<code>" in toks
    assert info["emoji_n"] >= 1

    # Pure numbers > 4 digits
    toks, info = cleaner.clean_and_tokenize("Values 123 and 123456 in sample")
    assert "123" in toks
    assert "<num>" in toks

    # Deleted / removed
    toks, info = cleaner.clean_and_tokenize("[deleted]")
    assert toks == [] and info["dropped"] == "deleted_removed_empty"

    print("  cleaner: PASS")


def test_storage_and_gensim_atomic():
    print("Testing src.storage...")
    root = paths.get_project_root()
    test_dir = root / "shards/temporary/test_storage_suite"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Atomic write text
    txt_file = test_dir / "sample.txt"
    storage.atomic_write_text(txt_file, "hello atomic storage")
    assert txt_file.exists() and txt_file.read_text() == "hello atomic storage"
    
    # SHA256 file
    h = storage.sha256_file(txt_file)
    expected_h = hashlib.sha256(b"hello atomic storage").hexdigest()
    assert h == expected_h, f"Hash mismatch: got {h}, expected {expected_h}"

    # Test save_gensim_atomic with companion .npy files
    class MockGensimModel:
        def save(self, path_str):
            # Writes main file plus simulated companion .npy files
            p = Path(path_str)
            with open(p, "w") as f: f.write("main model pickle")
            with open(p.with_name(p.name + ".vectors.npy"), "wb") as f: f.write(b"npy vector array")
            with open(p.with_name(p.name + ".syn1neg.npy"), "wb") as f: f.write(b"npy syn1 array")

    target_model = test_dir / "w2v__test__2019q1.model"
    storage.save_gensim_atomic(MockGensimModel(), target_model)
    
    assert target_model.exists()
    assert (test_dir / "w2v__test__2019q1.model.vectors.npy").exists(), "Companion vectors.npy missing!"
    assert (test_dir / "w2v__test__2019q1.model.syn1neg.npy").exists(), "Companion syn1neg.npy missing!"
    
    # Verify no .staging or .tmp files left over
    staging_dirs = list(test_dir.glob(".staging*"))
    assert len(staging_dirs) == 0, "Staging directory was not cleaned up!"
    
    # Cleanup
    shutil.rmtree(test_dir, ignore_errors=True)
    print("  storage & save_gensim_atomic: PASS")


def test_manifests():
    print("Testing src.manifests...")
    root = paths.get_project_root()
    test_dir = root / "shards/temporary/test_manifest_suite"
    test_dir.mkdir(parents=True, exist_ok=True)

    man_file = test_dir / "test_retrieval_manifest.csv"
    storage.atomic_write_text(man_file, ",".join(manifests.RETRIEVAL_COLS) + "\n")

    # Upsert row
    row1 = {"unit_id": "u1", "status": "in_progress", "n_read": 100}
    manifests.upsert_manifest_row(man_file, row1, ["unit_id"], manifests.RETRIEVAL_COLS)
    loaded = manifests.load_manifest(man_file)
    assert len(loaded) == 1
    assert loaded[0]["unit_id"] == "u1"
    assert loaded[0]["status"] == "in_progress"

    # Update row idempotently
    row1_upd = {"unit_id": "u1", "status": "complete", "n_read": 200}
    manifests.upsert_manifest_row(man_file, row1_upd, ["unit_id"], manifests.RETRIEVAL_COLS)
    loaded = manifests.load_manifest(man_file)
    assert len(loaded) == 1
    assert loaded[0]["status"] == "complete"
    assert loaded[0]["n_read"] == "200"

    # Test verify_output_shards
    s1 = test_dir / "shard1.gz"
    s2 = test_dir / "shard2.gz"
    storage.atomic_write_text(s1, "content1")
    storage.atomic_write_text(s2, "content2")
    h1 = storage.sha256_file(s1)
    h2 = storage.sha256_file(s2)

    # 1. Single file match
    assert manifests.verify_output_shards(str(s1), h1)
    # 2. Multi-file semicolon match
    assert manifests.verify_output_shards(f"{s1};{s2}", f"{h1};{h2}")
    # 3. Combined hash match (backward compatibility)
    comb = hashlib.sha256(f"{h1};{h2}".encode()).hexdigest()
    assert manifests.verify_output_shards(f"{s1};{s2}", comb)
    # 4. Mismatch detection
    assert not manifests.verify_output_shards(str(s1), "invalid_hash")
    assert not manifests.verify_output_shards(str(test_dir / "nonexistent.gz"), h1)

    # Cleanup
    shutil.rmtree(test_dir, ignore_errors=True)
    print("  manifests: PASS")


if __name__ == "__main__":
    test_paths()
    test_cleaner()
    test_storage_and_gensim_atomic()
    test_manifests()
    print("ALL UNIT TESTS PASSED SUCCESSFULLY!")
