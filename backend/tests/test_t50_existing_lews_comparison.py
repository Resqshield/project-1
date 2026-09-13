"""Acceptance checks for T50 existing EWS comparison."""

from pathlib import Path


DOC = Path("docs/m5/day2/T50_EXISTING_LEWS_COMPARISON.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_t50_document_exists() -> None:
    assert DOC.exists()


def test_strong_comparators_are_present() -> None:
    text = _text()

    required = (
        "Amrita-LEWS",
        "LANDSLIP",
        "South Asia FFGS",
        "GSI National Landslide Forecasting Centre",
    )

    for comparator in required:
        assert comparator in text


def test_comparison_has_exact_resqshield_difference_column() -> None:
    text = _text()

    assert "Exact ResQShield Difference" in text


def test_amrita_comparison_is_bounded() -> None:
    text = _text()

    assert "Do not claim India lacks operational IoT landslide EWS" in text
    assert "observation-confidence / source-health scoring" in text


def test_landslip_is_treated_as_hard_baseline() -> None:
    text = _text()

    assert "LANDSLIP should be implemented/reproduced conceptually as a HARD BASELINE." in text
    assert "rainfall thresholds are novel" in text


def test_ffgs_is_treated_as_authoritative_upstream_intelligence() -> None:
    text = _text()

    assert "ingest authoritative regional guidance as one trusted evidence source" in text
    assert "local sensing complements rather than substitutes authoritative forecasts" in text


def test_gsi_is_not_treated_as_replaceable() -> None:
    text = _text()

    assert "Do not claim India has no landslide forecasting" in text
    assert "replacement for GSI/NLFC" in text


def test_established_technologies_are_not_claimed_as_novelty() -> None:
    text = _text()

    required = (
        "AI/ML hazard modelling",
        "IoT sensor networks",
        "LoRa/wireless telemetry",
        "rainfall thresholds",
        "physics + ML hybrid models",
    )

    for item in required:
        assert item in text


def test_claimed_improvements_require_validation() -> None:
    text = _text()

    assert "These are target improvements and must be validated experimentally." in text
    assert "LANDSLIP-style threshold baseline tested on the same event split" in text


def test_judge_safe_positioning_exists() -> None:
    text = _text()

    assert "Strong Indian and regional systems already provide" in text
    assert "We are the first to use IoT/LoRa/AI for landslide warning." in text
    assert "Our model is better than existing systems." in text
