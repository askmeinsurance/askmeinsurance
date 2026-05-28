"""Import and environment setup that must happen before backend imports."""

import sys
from pathlib import Path

from dotenv import load_dotenv

from eval_utils.config import BACKEND_ROOT, EVALS_ROOT


def bootstrap_environment() -> None:
    for env_path in [EVALS_ROOT / ".env", EVALS_ROOT / "eval_utils" / ".env"]:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            break

    _prepend_sys_path(EVALS_ROOT)
    _prepend_sys_path(BACKEND_ROOT)


def _prepend_sys_path(path: Path) -> None:
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
