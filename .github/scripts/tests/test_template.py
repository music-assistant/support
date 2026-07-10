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
