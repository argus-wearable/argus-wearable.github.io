"""Rewrite the CAD download list in index.html from the CAD folder.

Run this after adding or removing printable files:

    python scripts/list_cad.py
"""

from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CAD = ROOT / "CAD"
INDEX = ROOT / "index.html"
START = "<!-- CAD:START -->"
END = "<!-- CAD:END -->"
DESCRIPTIONS = {
    "ArgusCore.stl": "rigid 3D-printed PLA electronics enclosure",
    "TPUMount.stl": "soft 3D-printed TPU cuff to interface with the limb",
}


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def render(files: list[Path]) -> str:
    if not files:
        return (
            '        <p class="empty">Printable files for the rigid enclosure and the '
            "TPU cuff will be listed here.</p>"
        )
    rows = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        name = path.relative_to(CAD).as_posix()
        href = quote(rel, safe="/")
        desc = DESCRIPTIONS.get(path.name, "")
        desc_html = (
            f'<span class="file-desc">{escape(desc)}</span>' if desc else ""
        )
        rows.append(
            '          <a class="file" href="{href}" download>'
            "<span><span class=\"file-name\">{name}</span>{desc}</span>"
            '<span class="file-meta">{size}</span>'
            "</a>".format(
                href=escape(href, quote=True),
                name=escape(name),
                desc=desc_html,
                size=escape(format_size(path.stat().st_size)),
            )
        )
    return '        <div class="file-list">\n' + "\n".join(rows) + "\n        </div>"


def main() -> None:
    files = sorted(
        p
        for p in CAD.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(CAD).parts)
    )
    text = INDEX.read_text(encoding="utf-8")
    try:
        start = text.index(START) + len(START)
        end = text.index(END, start)
    except ValueError as exc:
        raise SystemExit("CAD markers are missing from index.html") from exc
    updated = text[:start] + "\n" + render(files) + "\n" + text[end:]
    INDEX.write_text(updated, encoding="utf-8", newline="\n")
    if files:
        print(f"Listed {len(files)} CAD file(s).")
    else:
        print("CAD folder is empty. Wrote the placeholder.")


if __name__ == "__main__":
    main()
