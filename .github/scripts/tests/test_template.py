import re
from pathlib import Path

from ma_triage import config, template


def test_parse_sections():
    body = "### What happened?\n\nIt crashes\n\n### How to reproduce\n\nDo X"
    sections = template.parse_sections(body)
    assert sections["What happened?"] == "It crashes"
    assert sections["How to reproduce"] == "Do X"


def test_form_kind_from_labels():
    assert template.form_kind(["triage"]) == "main"
    assert template.form_kind(["triage", "frontend"]) == "frontend"
    assert template.form_kind(["triage", "translation"]) == "translation"
    # case-insensitive + tolerant of extra labels
    assert template.form_kind({"Frontend", "triage", "sonos"}) == "frontend"
    assert template.form_kind(None) == "main"


def _main_body(**overrides):
    fields = {
        "What happened?": "It crashes",
        "How to reproduce": "Open the app",
        "Music Assistant version": "2.9.0",
        "How do you run Music Assistant?": "Home Assistant add-on",
    }
    fields.update(overrides)
    return "\n".join(f"### {k}\n\n{v}" for k, v in fields.items())


def test_missing_sections_main_all_present():
    assert template.missing_sections(_main_body(), "main") == []


def test_missing_sections_main_detects_empty():
    body = _main_body(**{"What happened?": ""})
    missing = template.missing_sections(body, "main")
    assert "What happened?" in missing
    assert "How to reproduce" not in missing


def test_missing_sections_treats_no_response_as_empty():
    body = _main_body(**{"How to reproduce": config.NO_RESPONSE_SENTINEL})
    assert "How to reproduce" in template.missing_sections(body, "main")


def test_missing_sections_frontend_uses_frontend_fields():
    body = (
        "### Music Assistant version\n\n2.9.0\n\n"
        "### Browser and operating system\n\nFirefox on Linux\n\n"
        "### What happened?\n\nUI is blank\n\n"
        "### How to reproduce\n\nOpen settings"
    )
    assert template.missing_sections(body, "frontend") == []
    # install-method is NOT required on the frontend form
    assert "How do you run Music Assistant?" not in template.required_sections_for(
        "frontend"
    )


def test_extract_version_and_install_method():
    body = _main_body(**{"Music Assistant version": "2.8.1"})
    assert template.extract_version(body) == "2.8.1"
    assert template.extract_install_method(body) == "Home Assistant add-on"


def test_extract_version_none_when_no_response():
    body = _main_body(**{"Music Assistant version": config.NO_RESPONSE_SENTINEL})
    assert template.extract_version(body) is None


def test_provider_scan_text_includes_title_and_fields():
    body = _main_body(
        **{
            "What happened?": "Spotify stopped working",
            "Anything else?": "also affects Sonos",
        }
    )
    text = template.provider_scan_text(body, title="Playback fails on Chromecast")
    assert "Chromecast" in text
    assert "Spotify" in text
    assert "Sonos" in text


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


# --- boilerplate stripping ---------------------------------------------------- #
def test_strip_boilerplate_drops_the_consent_block():
    body = (
        "### Before you begin\n\n"
        "- [x] I have searched the [open and closed issues](https://x).\n"
        "- [X] I have read the [troubleshooting guide](https://y).\n\n"
        "### What happened?\n\nAirPlay goes silent when the group is joined"
    )
    stripped = template.strip_boilerplate(body)
    assert "Before you begin" not in stripped
    assert "troubleshooting guide" not in stripped
    assert "### What happened?" in stripped
    assert "AirPlay goes silent when the group is joined" in stripped


def test_strip_boilerplate_covers_every_form_generation():
    """The index reaches back to 2022, so all four wordings are live at once."""
    for heading in (
        "Before you begin",
        "Carefully read the Troubleshooting FAQ and confirm that",
        "Mandatory: Carefully read the Troubleshooting FAQ and confirm that",
        "As Applicable: Carefully read the Troubleshooting FAQ and confirm that",
        "Have you tried everything in the Troubleshooting FAQ and reviewed the "
        "Open and Closed Issues and Discussions to resolve this yourself?",
        "Have you included ALL of the information specified in the "
        "Troubleshooting FAQ or explained why you cannot",
        "Have you reviewed the [Open](https://a) and [Closed](https://b) Issues "
        "to resolve this yourself?",
    ):
        stripped = template.strip_boilerplate(
            f"### {heading}\n\n- [x] Yes\n\n### The problem\n\nNo sound"
        )
        assert heading.split("[")[0].strip() not in stripped, heading
        assert "No sound" in stripped


def test_strip_boilerplate_keeps_logs_and_headings():
    """Error text is what makes two reports the same; it has to survive."""
    body = (
        "### What happened?\n\nPlayback fails\n\n"
        "```\n2026-08-14 ERROR [ffmpeg.1065] Invalid data found\n```\n\n"
        "### Anything else?\n\nNothing"
    )
    stripped = template.strip_boilerplate(body)
    assert "ERROR [ffmpeg.1065] Invalid data found" in stripped
    assert "### What happened?" in stripped and "### Anything else?" in stripped


def test_strip_boilerplate_removes_inline_checkboxes():
    stripped = template.strip_boilerplate(
        "### The problem\n\n- [ ] not yet done\nReal text here"
    )
    assert "not yet done" not in stripped and "Real text here" in stripped


def test_strip_boilerplate_handles_empty_input():
    assert template.strip_boilerplate(None) == ""
    assert template.strip_boilerplate("") == ""


# --- a replaced form is not a missing field ------------------------------------ #
_NO_FORM = (
    "# Sonos sync_group reports state 'idle'\n\n"
    "## Environment\n\nMA 2.10.1, HA add-on\n\n"
    "## Analysis\n\nThe provider returns the wrong state because "
) + "x" * 1600


def test_form_replaced_when_a_long_report_answers_none_of_the_form():
    assert template.form_replaced(_NO_FORM, "main") is True


def test_form_replaced_ignores_a_short_report_with_no_form():
    """Terse is not the same problem, and the advice would be wrong."""
    assert template.form_replaced("It broke. Please fix.", "main") is False


def test_form_replaced_ignores_a_report_that_used_the_form():
    body = _main_body()
    assert template.form_replaced(body + "x" * 3000, "main") is False


def test_form_replaced_only_applies_to_the_main_form():
    assert template.form_replaced(_NO_FORM, "frontend") is False
    assert template.form_replaced(_NO_FORM, "translation") is False


def test_required_sections_match_the_form_that_ships():
    """The constants claim to be kept in sync with the issue form by hand.

    Nothing enforced that, and the risk changed with `form_replaced`: a stale
    heading used to mean a redundant "please fill this in", and now means every
    correctly-filed report is told it bypassed the form. A one-word label edit
    should fail here rather than in production.
    """
    form = Path(__file__).resolve().parents[2] / "ISSUE_TEMPLATE" / "1_bug_report.yml"
    labels = set(re.findall(r"^\s*label:\s*(.+?)\s*$", form.read_text(), re.M))
    missing = [s for s in template.REQUIRED_SECTIONS_MAIN if s not in labels]
    assert not missing, f"not in {form.name}: {missing}"


def test_form_replaced_threshold_is_tunable(monkeypatch):
    """The floor is the knob to reach for during rollout, so it has to work."""
    monkeypatch.setattr(config, "FORM_REPLACED_MIN_CHARS", 10_000)
    assert template.form_replaced(_NO_FORM, "main") is False
