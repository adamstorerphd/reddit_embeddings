import os
import sys
from pathlib import Path
from typing import Optional


def _has_root_marker(p: Path) -> bool:
    """A valid project root is a directory containing the config file."""
    try:
        return p.is_dir() and (p / "config/project_config.yaml").is_file()
    except OSError:
        return False


def _find_root(start: Path) -> Optional[Path]:
    """Search upward, then a bounded depth downward, for the repo root."""
    for p in [start, *start.parents]:
        if _has_root_marker(p):
            return p
    for depth in (1, 2):
        for sub in start.glob("/".join(["*"] * depth)):
            if sub.is_dir() and _has_root_marker(sub):
                return sub
    return None


def get_project_root(drive_root: str = "/content/drive/MyDrive/reddit_embeddings_project") -> Path:
    """Resolve the project root across Google Colab and local environments.

    Checks in order:
      1. The canonical Google Drive clone location (if mounted and present).
      2. The current working directory and its parents (locating
         ``config/project_config.yaml``), then a bounded search *beneath* cwd so
         the repo is found even when the notebook is launched from a parent
         directory (e.g. a workspace root that contains the checkout).
      3. In Colab, the Google Drive mount (catches alternate clone names).
      4. Relative to this file (the repo root is the parent of ``src/``).

    Adds the resolved root to ``sys.path`` so ``src`` imports work, and raises a
    clear ``RuntimeError`` (instead of silently returning a non-existent path)
    if the root cannot be located.
    """
    drive_p = Path(drive_root)

    # 1. Canonical Colab Drive location.
    if _has_root_marker(drive_p):
        root = drive_p.resolve()
    else:
        # 2. Search upward from cwd, then a bounded depth downward.
        cwd = Path.cwd().resolve()
        root = _find_root(cwd)

        # 3. In Colab, also search the Drive mount for alternate clone names.
        if root is None and drive_p.parent.is_dir():
            root = _find_root(drive_p.parent)

        # 4. Relative to this file (repo root is parent of src/).
        if root is None:
            file_root = Path(__file__).resolve().parent.parent
            if _has_root_marker(file_root):
                root = file_root

    if root is None:
        raise RuntimeError(
            "Cannot locate the project root (a directory containing "
            "'config/project_config.yaml' and 'src/'). Mount Drive and cd to the "
            "checkout, or clone the repo into Google Drive, or run from inside the repo."
        )

    root = root.resolve()
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
