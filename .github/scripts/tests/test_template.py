from ma_triage import config, template


def test_parse_sections():
    body = "### The problem\n\nIt crashes\n\n### How to reproduce\n\nDo X"
    sections = template.parse_sections(body)
    assert sections["The problem"] == "It crashes"
    assert sections["How to reproduce"] == "Do X"


def test_missing_sections_detects_empty():
    body = "### The problem\n\n\n### How to reproduce\n\nsteps"
    missing = template.missing_sections(body)
    assert "The problem" in missing
    assert "How to reproduce" not in missing


def test_missing_sections_all_present():
    body = "### The problem\n\nreal detail here\n\n### How to reproduce\n\nreal steps here"
    assert template.missing_sections(body) == []


def test_detect_log_wall_by_lines():
    lines = "\n".join(
        f"2024-05-01 12:00:0{i%10} ERROR something happened {i}" for i in range(40)
    )
    assert template.detect_log_wall(lines) is True


def test_detect_log_wall_fenced():
    inner = "\n".join(f"ERROR line {i}" for i in range(40))
    body = f"here is my log:\n```\n{inner}\n```"
    assert template.detect_log_wall(body) is True


def test_no_log_wall_for_short_body():
    assert template.detect_log_wall("just a short description") is False
