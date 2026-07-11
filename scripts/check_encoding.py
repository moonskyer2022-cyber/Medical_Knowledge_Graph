"""Fail fast when project text files are not valid UTF-8."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = {".py", ".js", ".html", ".css", ".md", ".yml", ".yaml", ".json", ".csv", ".ps1"}
SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__"}
LEGACY_DOC_PREFIXES = ("docs/FSE-", "docs/star.md")


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT).as_posix()
        if (not path.is_file() or path.suffix.lower() not in EXTENSIONS
                or SKIP_PARTS.intersection(path.parts)
                or relative.startswith(LEGACY_DOC_PREFIXES)):
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(str(path.relative_to(ROOT)))
    if failures:
        print("非 UTF-8 文件：")
        print("\n".join(failures))
        return 1
    print("UTF-8 编码检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
