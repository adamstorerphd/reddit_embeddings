import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Any, Union


def sha256_file(p: Union[str, Path]) -> str:
    """Compute SHA256 of file in 1MB chunks."""
    p = Path(p)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_bytes(path: Union[str, Path], data: bytes) -> None:
    """Atomic write bytes via .tmp file with fsync."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp_{int(time.time()*1000)}")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    assert tmp.stat().st_size > 0, f"Refusing to write empty file {path}"
    os.replace(tmp, path)


def atomic_write_text(path: Union[str, Path], text: str, encoding: str = "utf-8") -> None:
    """Atomic write text via .tmp file with fsync."""
    atomic_write_bytes(path, text.encode(encoding))


def save_gensim_atomic(model_or_wv: Any, target_path: Union[str, Path]) -> None:
    """Atomically save a Gensim Word2Vec or KeyedVectors object.
    
    Gensim automatically splits large NumPy arrays (>10MB) into companion
    files like <target>.vectors.npy and <target>.syn1neg.npy.
    Saving to a staging folder preserves all companion files with their exact
    target names and avoids leaving orphaned .tmp.npy files that break loading.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = target_path.parent / f".staging_{target_path.stem}_{int(time.time()*1000)}"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_target = staging_dir / target_path.name
    
    try:
        model_or_wv.save(str(staging_target))
        # Atomically move each generated file to final destination
        for p in staging_dir.iterdir():
            dest = target_path.parent / p.name
            os.replace(p, dest)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
    
    assert target_path.exists() and target_path.stat().st_size > 0, f"Failed to save {target_path}"
