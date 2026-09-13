"""Acceptance checks for T66 EWS claim separation documentation."""

from pathlib import Path


DOC = Path("docs/m5/day2/T66_EW4ALL_CLAIM_SEPARATION.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_t66_document_exists() -> None:
    assert DOC.exists()


def test_all_23_modules_are_classified() -> None:
    text = _text()
    rows = [
        line
        for line in text.splitlines()
        if line.startswith("| M") and len(line) >= 5 and line[3:5].isdigit()
    ]
    assert len(rows) == 23


def test_four_ews_stages_are_present() -> None:
    text = _text()

    required = (
        "Stage 1 — Risk Knowledge",
        "Stage 2 — Monitoring / Forecasting",
        "Stage 3 — Warning Dissemination / Communication",
        "Stage 4 — Preparedness / Response Capability",
    )

    for heading in required:
        assert heading in text


def test_claim_categories_are_separated() -> None:
    text = _text()

    required = (
        "### Monitoring",
        "### Detection",
        "### Prediction",
        "### Warning",
        "### Action / Response",
        "### Validation / Support",
    )

    for heading in required:
        assert heading in text


def test_static_susceptibility_not_equated_to_prediction() -> None:
    text = _text()

    assert "Static susceptibility is not prediction" in text


def test_monitoring_not_equated_to_prediction() -> None:
    text = _text()

    assert "Sensor monitoring is not prediction" in text


def test_prediction_not_equated_to_warning() -> None:
    text = _text()

    assert "Prediction is not warning" in text


def test_warning_not_equated_to_complete_ews() -> None:
    text = _text()

    assert "Warning delivery is not the whole EWS" in text


def test_ai_iot_lora_are_not_claimed_as_novelty_by_themselves() -> None:
    text = _text()

    assert "AI / IoT / LoRa are enabling technologies" in text


def test_route_claim_is_bounded() -> None:
    text = _text()

    assert "lowest-known-risk recommended route" in text
    assert "guaranteed safe route" in text


def test_validation_scope_rule_exists() -> None:
    text = _text()

    assert "Simulation/replay evidence is not described as field-proven evidence." in text
