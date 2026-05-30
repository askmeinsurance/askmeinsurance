from __future__ import annotations

import argparse
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def default_output_dir() -> str:
    return os.getenv("PIPELINE_OUTPUT_DIR", "output")


def source_stem(file_name: str) -> str:
    return Path(file_name).stem


def collect_targets(output_root: Path, stem: str) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    dirs: list[Path] = []

    # Primary directory created by step1_mineru_convert.py
    mineru_dir = output_root / "mineru" / stem
    if mineru_dir.exists() and mineru_dir.is_dir():
        dirs.append(mineru_dir)

    # Files associated with this document across output subtree.
    for path in output_root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if path.stem == stem or name.startswith(f"{stem}.") or name.startswith(f"{stem}_"):
            files.append(path)

    # Remove duplicates while preserving order.
    dedup_files = list(dict.fromkeys(files))
    dedup_dirs = list(dict.fromkeys(dirs))
    return dedup_files, dedup_dirs


def delete_targets(files: list[Path], dirs: list[Path], dry_run: bool) -> None:
    for file_path in files:
        if dry_run:
            logger.info("[dry-run] delete file: %s", file_path)
            continue
        file_path.unlink(missing_ok=True)
        logger.info("Deleted file: %s", file_path)

    for dir_path in dirs:
        if dry_run:
            logger.info("[dry-run] delete directory: %s", dir_path)
            continue
        shutil.rmtree(dir_path, ignore_errors=True)
        logger.info("Deleted directory: %s", dir_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete output artifacts associated with a file name (by stem)."
    )
    parser.add_argument(
        "--file",
        required=True,
        help="File name or stem (e.g. 'aia_whole_life_dividends.pdf' or 'aia_whole_life_dividends').",
    )
    parser.add_argument("--output-dir", default=default_output_dir())
    parser.add_argument("--dry-run", action="store_true", help="Preview deletions without removing anything.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )

    output_root = Path(args.output_dir)
    if not output_root.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_root}")

    stem = source_stem(args.file)
    files, dirs = collect_targets(output_root, stem)

    logger.info("Target stem: %s", stem)
    logger.info("Matched %d files and %d directories under %s", len(files), len(dirs), output_root)

    if not files and not dirs:
        logger.info("Nothing to delete.")
        return

    delete_targets(files, dirs, args.dry_run)


if __name__ == "__main__":
    main()
