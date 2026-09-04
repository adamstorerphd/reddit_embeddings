import os
import sys
from pathlib import Path
from typing import Optional


def get_project_root(drive_root: str = "/content/drive/MyDrive/reddit_embeddings_project") -> Path:
    """Resolve project root across Google Colab and local environments.
    
    Checks in order:
    1. Colab Google Drive path (if present and mounted)
    2. Current working directory and its parents (locating config/project_config.yaml)
    3. File parent directory
    4. Fallback to drive_root
    
    Ensures root is added to sys.path so 'src' imports work seamlessly.
    """
    # 1. Colab Drive check
    drive_p = Path(drive_root)
    if drive_p.exists() and (drive_p / "config/project_config.yaml").exists():
        root = drive_p.resolve()
    else:
        # 2. Search upwards from cwd
        cwd = Path.cwd().resolve()
        found = None
        for p in [cwd, *cwd.parents]:
            if (p / "config/project_config.yaml").exists():
                found = p
                break
        if found is not None:
            root = found
        else:
            # 3. Search relative to this file
            file_root = Path(__file__).resolve().parent.parent
            if (file_root / "config/project_config.yaml").exists():
                root = file_root
            else:
                root = drive_p

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def resolve_tmp(root: Path, cfg: Optional[dict] = None) -> Path:
    """Resolve scratch directory with Colab / local fallback."""
    if cfg and "paths" in cfg and "colab_tmp" in cfg["paths"]:
        cand = Path(cfg["paths"]["colab_tmp"])
        try:
            cand.mkdir(parents=True, exist_ok=True)
            return cand
        except Exception:
            pass
    tmp = root / "shards/temporary"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp
