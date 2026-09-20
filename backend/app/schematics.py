"""FRS / P&ID structured view (blueprint: FRS & P&ID viewer).

The 17-section lifecycle stores P&ID loop tables ('p_and_id'), the I/O list and
the tag list as markdown. This module parses those tables into structured,
renderable data so the viewer can show the instrument loops, I/O card map and
tag register side-by-side with the FRS column — no drawing needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Project, ProjectSection


def _markdown_tables(md: str) -> list[list[dict[str, str]]]:
    """Extract markdown tables as lists of row dicts (header keys)."""
    tables: list[list[dict[str, str]]] = []
    header: list[str] | None = None
    rows: list[dict[str, str]] = []

    def flush() -> None:
        nonlocal header, rows
        if header is not None and rows:
            tables.append(rows)
        header = None
        rows = []

    for raw in (md or "").splitlines():
        line = raw.strip()
        if not line.startswith("|") or not line.endswith("|"):
            flush()
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            rows = []
            continue
        if all(re.match(r"^[-: ]+$", c) for c in cells if c):
            continue
        rows.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)})
    flush()
    return tables


def _section(db: Session, project_id: int, key: str) -> str:
    row = (
        db.query(ProjectSection)
        .filter(ProjectSection.project_id == project_id, ProjectSection.key == key)
        .first()
    )
    return row.content if row else ""


@dataclass
class Schematic:
    project_id: int
    slug: str
    title: str
    instruments: list[dict] = field(default_factory=list)
    io: list[dict] = field(default_factory=list)
    tags: list[dict] = field(default_factory=list)
    loops: list[dict] = field(default_factory=list)
    note: str = ""


def build_schematic(db: Session, project: Project) -> Schematic:
    p_and_id = _section(db, project.id, "p_and_id")
    io_list = _section(db, project.id, "io_list")
    tag_list = _section(db, project.id, "tag_list")

    instruments: list[dict] = []
    for table in _markdown_tables(p_and_id):
        for row in table:
            tag = next((v for k, v in row.items() if str(k).lower() == "tag"), "")
            if tag:
                instruments.append(
                    {
                        "tag": tag,
                        "service": row.get("Service", ""),
                        "signal": row.get("Signal", ""),
                        "card": row.get("Card", ""),
                        "range": row.get("Range", ""),
                    }
                )

    io: list[dict] = []
    for table in _markdown_tables(io_list):
        for row in table:
            addr = next((v for k, v in row.items() if str(k).lower() == "address"), "")
            tag = next((v for k, v in row.items() if str(k).lower() == "tag"), "")
            if tag and addr:
                io.append(
                    {
                        "module": row.get("Module", ""),
                        "address": addr,
                        "tag": tag,
                        "description": row.get("Description", ""),
                        "type": row.get("Type", ""),
                        "range": row.get("Range", ""),
                        "loop": row.get("Loop", ""),
                    }
                )

    tags: list[dict] = []
    for table in _markdown_tables(tag_list):
        for row in table:
            tag = next((v for k, v in row.items() if str(k).lower() == "tag"), "")
            if tag:
                tags.append(
                    {
                        "tag": tag,
                        "description": row.get("Description", ""),
                        "datatype": row.get("Data type", row.get("Datatype", "")),
                        "units": row.get("Units", ""),
                        "range": row.get("Range", ""),
                        "alias": row.get("Alias", ""),
                    }
                )

    return Schematic(
        project_id=project.id,
        slug=project.slug,
        title=project.title,
        instruments=instruments,
        io=io,
        tags=tags,
        loops=[dict(i) for i in instruments],
        note="Extracted from the project's P&ID, I/O list and Tag List sections (ISA-5.1 / IEC 61131-3).",
    )