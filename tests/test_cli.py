from docx import Document

from toolkit.cli import main


def test_demo_end_to_end(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SAMPLE / DEMO DATA" in out
    docx = next((tmp_path / "agenda").glob("*.docx"))
    text = "\n".join(p.text for p in Document(docx).paragraphs)
    assert "Q4 Operations Steering Committee" in text
    assert next((tmp_path / "agenda").glob("*.ics")).read_text().startswith("BEGIN:VCALENDAR")
    assert (tmp_path / "expenses" / "expense_tracker.xlsx").exists()
    assert list((tmp_path / "kpi").glob("*.png"))


def test_agenda_rejects_bad_pick(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        main(["agenda", "--pick", "99", "--out", str(tmp_path)])


def test_slots_returns_nonzero_when_impossible(tmp_path, capsys):
    rc = main(["slots", "--start", "2026-11-06", "--end", "2026-11-07"])  # Fri-Sat only
    assert rc == 1
    assert "No slot" in capsys.readouterr().out
