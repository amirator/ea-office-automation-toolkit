import pytest

from conftest import SAMPLE
from toolkit.kpi import assess, load_kpis, rag_status, render


@pytest.mark.parametrize("actual,target,direction,tol,expected", [
    (95, 90, "higher", 5, "Green"),
    (88, 90, "higher", 5, "Amber"),   # within 5% (85.5)
    (80, 90, "higher", 5, "Red"),
    (100, 100, "lower", 5, "Green"),
    (104, 100, "lower", 5, "Amber"),
    (112, 100, "lower", 5, "Red"),
])
def test_rag_status(actual, target, direction, tol, expected):
    assert rag_status(actual, target, direction, tol) == expected


def test_sample_pack_status_counts():
    period, rows = assess(load_kpis(SAMPLE / "kpis.csv"))
    assert period == "2026-09"
    assert len(rows) == 8
    statuses = {r["kpi"].name: r["status"] for r in rows}
    assert statuses["IT tickets resolved within SLA"] == "Red"
    assert statuses["Board actions closed on time"] == "Green"


def test_render_writes_pdf_and_png(tmp_path):
    res = render(load_kpis(SAMPLE / "kpis.csv"), tmp_path)
    assert res["pdf"].stat().st_size > 10_000
    assert res["png"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_bad_direction_rejected():
    with pytest.raises(ValueError):
        rag_status(1, 1, "sideways", 5)
