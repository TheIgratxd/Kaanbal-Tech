from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "project_context.txt"
MAX_FILE_BYTES = 2 * 1024 * 1024

EXCLUDED_DIRECTORIES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "env",
    "node_modules",
    "venv",
}
EXCLUDED_SUFFIXES = {
    ".csv",
    ".db",
    ".log",
    ".pem",
    ".p12",
    ".pfx",
    ".pyc",
    ".sqlite",
    ".tsbuildinfo",
}
SENSITIVE_NAME_PARTS = (
    "accesskey",
    "credential",
    "privatekey",
    "secret",
)


def should_exclude(path: Path) -> bool:
    name = path.name.lower()
    if name.startswith(".env") or name == OUTPUT.name.lower():
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if any(part in name.replace("_", "").replace("-", "") for part in SENSITIVE_NAME_PARTS):
        return True
    return any(part.lower() in EXCLUDED_DIRECTORIES for part in path.parts)


def collect_files() -> list[Path]:
    files: list[Path] = []
    for current, directories, filenames in os.walk(ROOT, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name
            for name in directories
            if not should_exclude(current_path / name)
        )
        for filename in sorted(filenames):
            path = current_path / filename
            if not should_exclude(path) and not path.is_symlink():
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix().lower())


def render_tree(files: list[Path]) -> str:
    entries: set[str] = set()
    for path in files:
        relative = path.relative_to(ROOT)
        for parent in reversed(relative.parents):
            if parent != Path("."):
                entries.add(parent.as_posix().rstrip("/") + "/")
        entries.add(relative.as_posix())
    return "\n".join(sorted(entries, key=str.lower))


def main() -> None:
    files = collect_files()
    sections = [
        "PROJECT CONTEXT EXPORT",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "Includes readable project source, configuration, and documentation.",
        "Excludes environment files, CSV data, likely credential files, dependencies, "
        "generated artifacts, and binary files.",
        "",
        "PROJECT TREE",
        render_tree(files),
        "",
        "FILE CONTENTS",
    ]

    included = 0
    skipped = 0
    for path in files:
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                skipped += 1
                continue
            content = path.read_bytes()
            if b"\0" in content:
                skipped += 1
                continue
            text = content.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            skipped += 1
            continue

        relative = path.relative_to(ROOT).as_posix()
        sections.extend(
            [
                "",
                f"===== BEGIN FILE: {relative} =====",
                text.rstrip(),
                f"===== END FILE: {relative} =====",
            ]
        )
        included += 1

    OUTPUT.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(f"Export written: {OUTPUT}")
    print(f"Text files included: {included}")
    print(f"Files skipped (binary, unreadable, or over 2 MiB): {skipped}")
    print(f"Output size: {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
