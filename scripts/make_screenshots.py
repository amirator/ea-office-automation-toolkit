"""Render PNG screenshots of the real demo outputs into docs/ for the README.

Requires LibreOffice (soffice) and poppler (pdftoppm) on PATH. Run `make demo` first.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
OUT, DOCS = ROOT / "outputs", ROOT / "docs"


def run(*cmd):
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)


def pdf_page_png(pdf: Path, page: int, dest: Path, dpi: int = 110) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "p"
        run("pdftoppm", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page), "-singlefile", str(pdf), str(stem))
        shutil.move(f"{stem}.png", dest)


def autocrop(path: Path, pad: int = 24, bg: str = "white") -> None:
    """Trim the white page margins LibreOffice adds around a spreadsheet print-out."""
    im = Image.open(path).convert("RGB")
    bbox = ImageChops.difference(im, Image.new("RGB", im.size, bg)).getbbox()
    if bbox:
        l, t, r, b = bbox
        im.crop((max(l - pad, 0), max(t - pad, 0), min(r + pad, im.width), min(b + pad, im.height))).save(path)


def terminal_png(text: str, dest: Path, title: str) -> None:
    """Render captured CLI output as a terminal-style PNG (the text is real program output)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lines = text.rstrip().splitlines()
    width = max(len(ln) for ln in lines)
    fig = plt.figure(figsize=(0.083 * width + 0.6, 0.19 * len(lines) + 0.7), dpi=130)
    fig.patch.set_facecolor("#1E2430")
    fig.text(0.012, 0.985, title, color="#8B949E", family="DejaVu Sans Mono", fontsize=8.5, va="top")
    fig.text(0.012, 0.985 - 0.32 / fig.get_figheight(), "\n".join(lines), color="#E6EDF3",
             family="DejaVu Sans Mono", fontsize=8.5, va="top", linespacing=1.35)
    fig.savefig(dest, facecolor=fig.get_facecolor())
    plt.close(fig)
    autocrop(dest, pad=28, bg="#1E2430")


def to_pdf(src: Path, outdir: Path) -> Path:
    run(shutil.which("soffice") or "soffice", "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(src))
    return outdir / (src.stem + ".pdf")


def main() -> int:
    for tool in ("soffice", "pdftoppm"):
        if not shutil.which(tool):
            print(f"missing {tool}; install LibreOffice and poppler-utils", file=sys.stderr)
            return 1
    DOCS.mkdir(exist_ok=True)
    agenda_pdf = next((OUT / "agenda").glob("agenda_*.pdf"), None) or to_pdf(next((OUT / "agenda").glob("*.docx")),
                                                                              OUT / "agenda")
    pdf_page_png(agenda_pdf, 1, DOCS / "agenda.png")

    with tempfile.TemporaryDirectory() as tmp:
        xpdf = to_pdf(OUT / "expenses" / "expense_tracker.xlsx", Path(tmp))
        # Page order follows sheet order: Summary, Expenses, Trips, Policy, FX Rates.
        for page, name in ((1, "expenses_summary.png"), (2, "expenses_lines.png"), (3, "expenses_trips.png")):
            pdf_page_png(xpdf, page, DOCS / name, dpi=190 if page > 1 else 130)
            autocrop(DOCS / name)

    cli = subprocess.run([sys.executable, "-m", "toolkit", "slots", "--results", "3"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    terminal_png(cli, DOCS / "cli_slots.png", "$ python -m toolkit slots --results 3")

    shutil.copy(next((OUT / "kpi").glob("kpi_pack_*.png")), DOCS / "kpi_pack.png")
    for p in sorted(DOCS.glob("*.png")):
        print(f"  {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
