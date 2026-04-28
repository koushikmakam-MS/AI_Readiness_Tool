"""Unit tests for ai_readiness.personas.registry."""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_readiness.personas import load_persona_registry


def test_builtin_personas_loaded() -> None:
    reg = load_persona_registry()
    expected = {
        "onboarding",
        "bug_fix",
        "feature_builder",
        "refactor",
        "ops_deploy",
        "api_consumer",
        "security_review",
        "architecture",
        "test_qa",
    }
    assert expected.issubset(reg.personas.keys())
    dora = reg.get("onboarding")
    assert dora is not None
    assert "Dora" in dora.display_name
    assert dora.prompt_template  # loaded from prompts/dora.md


def test_yaml_override_disables_persona(tmp_path: Path) -> None:
    cfg = tmp_path / "personas.yaml"
    cfg.write_text(
        yaml.dump(
            {
                "top_k": 10,
                "personas": {
                    "ops_deploy": {"enabled": False, "weight": 0.5},
                },
            }
        ),
        encoding="utf-8",
    )
    reg = load_persona_registry(cfg)
    assert reg.top_k == 10
    ops = reg.get("ops_deploy")
    assert ops is not None
    assert ops.enabled is False
    assert ops.weight == 0.5
    assert all(p.persona_id != "ops_deploy" for p in reg.enabled())


def test_select_unknown_id_warns_and_skips() -> None:
    reg = load_persona_registry()
    selected = reg.select(["onboarding", "does_not_exist"])
    ids = [p.persona_id for p in selected]
    assert ids == ["onboarding"]
