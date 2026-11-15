"""Write a generated block into a hand-written doc, between markers, so regenerating never touches the rest.

    <!-- generated:<name> start -->  ...  <!-- generated:<name> end -->

The generated Markdown's headings are demoted by ``levels`` so its own title fits under the doc's sections.
"""
from __future__ import annotations

from pathlib import Path


def demote(markdown: str, levels: int = 1) -> str:
    out, fence = [], False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("#"):
            line = "#" * levels + line
        out.append(line)
    return "\n".join(out).strip() + "\n"


def write_section(path: Path, name: str, markdown: str, levels: int = 1) -> None:
    start, end = f"<!-- generated:{name} start -->", f"<!-- generated:{name} end -->"
    block = f"{start}\n\n{demote(markdown, levels)}\n{end}"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if start in text and end in text:
        head, rest = text.split(start, 1)
        _, tail = rest.split(end, 1)
        text = head + block + tail
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8")
