"""Shared helpers: CSV loading (with '#' comment lines), paths and brand colours."""

from __future__ import annotations

import csv
import io
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "sample_data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

SAMPLE_BANNER = "SAMPLE / DEMO DATA - fictional company (Demo Holding Co.); not real data"

# A restrained palette used by every output so the three tools look like one product.
NAVY = "1F3A5F"
TEAL = "2A9D8F"
LIGHT = "F4F6F8"
GREY = "6B7280"
RAG_COLOURS = {"Green": "2E9E5B", "Amber": "F2A93B", "Red": "D64545"}


def read_csv(path: str | Path) -> list[dict[str, str]]:
    """Read a CSV into a list of dicts, ignoring lines that start with '#'.

    Sample files carry a '# SAMPLE / DEMO DATA' first line so nobody mistakes
    them for real records; this keeps that label without breaking parsing.
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
