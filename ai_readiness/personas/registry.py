"""Built-in persona definitions and YAML override loader."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from ai_readiness.personas.base import PersonaDefinition

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# (persona_id, display_name, role, prompt_file, interests, simulated_task, weight)
_BUILTIN: tuple[tuple[str, str, str, str, str, str, float], ...] = (
    (
        "onboarding",
        "Dora the Explorer",
        "Onboarding Agent",
        "dora.md",
        "Project purpose, scope, languages/frameworks, top-level architecture, "
        "where to start reading, install/run/test instructions, glossary.",
        "In 5 bullet points, explain what this repo does, what stack it uses, "
        "and the exact commands to install, run, and test it locally.",
        1.0,
    ),
    (
        "bug_fix",
        "Sherlock Hound",
        "Bug-Fix Agent",
        "sherlock.md",
        "Module ownership, error/exception handling, logging, debugging tips, "
        "known issues, troubleshooting guides, common failure modes.",
        "A user reports an unhandled error during a typical workflow. Identify "
        "the most likely module to investigate and the steps to reproduce.",
        1.0,
    ),
    (
        "feature_builder",
        "Bob the Builder",
        "Feature-Builder Agent",
        "bob.md",
        "Architecture overview, extension points, plugin/checker patterns, "
        "naming conventions, where new code is added, wiring/registration.",
        "Describe the steps and files needed to add a brand-new feature module "
        "to this project, using only the documentation as a guide.",
        1.0,
    ),
    (
        "refactor",
        "Handy Manny",
        "Refactor Agent",
        "handy_manny.md",
        "Public contracts, invariants, deprecation policies, test coverage "
        "guarantees, behavioural compatibility notes.",
        "List the public API surface and the invariants you must preserve when "
        "refactoring this codebase.",
        1.0,
    ),
    (
        "ops_deploy",
        "Postman Pat",
        "Ops/Deploy Agent",
        "postman_pat.md",
        "Build commands, run/start scripts, CI/CD configuration, environment "
        "variables, deployment targets, rollback steps, monitoring.",
        "Produce the exact commands and config required to build, run, and "
        "deploy this project to production.",
        1.0,
    ),
    (
        "api_consumer",
        "Mickey Mouse",
        "API Consumer Agent",
        "mickey.md",
        "Public API/SDK reference, examples, authentication, versioning, "
        "error model, client libraries, quickstarts.",
        "Without reading source code, explain how to call the public API, "
        "authenticate, and handle errors.",
        1.0,
    ),
    (
        "security_review",
        "Inspector Gadget",
        "Security Review Agent",
        "inspector_gadget.md",
        "Threat model, authentication/authorization, secrets handling, data "
        "flow, dependency hygiene, sensitive-data classification.",
        "Summarise the security posture: how secrets are handled, what trust "
        "boundaries exist, and the top 3 risks visible from documentation.",
        1.0,
    ),
    (
        "architecture",
        "Pinky & The Brain",
        "Architecture Agent",
        "brain.md",
        "System diagrams, module boundaries, data flow, design rationale, "
        "ADRs, technology choices, scalability/reliability notes.",
        "Sketch the high-level architecture (components + data flow) using "
        "only what the docs say.",
        1.0,
    ),
    (
        "test_qa",
        "Scooby-Doo",
        "Test/QA Agent",
        "scooby.md",
        "Test strategy, fixtures, coverage targets, how to run the test "
        "suite, flake notes, mocking patterns, QA checklists.",
        "Explain how to run the full test suite, where fixtures live, and "
        "where coverage is weakest.",
        1.0,
    ),
)


@dataclass
class PersonaRegistry:
    """Holds all loaded persona definitions plus run-level config."""

    personas: dict[str, PersonaDefinition] = field(default_factory=dict)
    prompt_version: str = "v1"
    top_k: int = 30
    max_chunk_chars: int = 8000
    weights: dict[str, float] = field(default_factory=dict)
    prices: dict[str, dict[str, float]] = field(default_factory=dict)
    simulated_tasks_enabled: bool = True

    def enabled(self) -> list[PersonaDefinition]:
        return [p for p in self.personas.values() if p.enabled]

    def get(self, persona_id: str) -> Optional[PersonaDefinition]:
        return self.personas.get(persona_id)

    def select(self, ids: list[str]) -> list[PersonaDefinition]:
        out: list[PersonaDefinition] = []
        for pid in ids:
            p = self.get(pid)
            if p is None:
                logger.warning("Unknown persona id: %s", pid)
                continue
            out.append(p)
        return out


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Missing prompt file: %s", path)
        return f"You are an AI persona. Score the doc 1-5 and return JSON. (Missing prompt: {filename})"


def _build_builtins() -> dict[str, PersonaDefinition]:
    out: dict[str, PersonaDefinition] = {}
    for pid, display, role, prompt_file, interests, task, weight in _BUILTIN:
        out[pid] = PersonaDefinition(
            persona_id=pid,
            display_name=display,
            role=role,
            interests=interests,
            simulated_task=task,
            prompt_template=_load_prompt(prompt_file),
            weight=weight,
            enabled=True,
        )
    return out


def load_persona_registry(
    config_path: Optional[Path] = None,
) -> PersonaRegistry:
    """Load built-in personas, then merge YAML overrides if present."""
    registry = PersonaRegistry(
        personas=_build_builtins(),
        weights={pid: 1.0 for pid in _BUILTIN_IDS},
    )

    if config_path and config_path.is_file():
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg: dict[str, Any] = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            logger.warning("Could not parse %s; using built-in defaults.", config_path)
            return registry

        registry.prompt_version = cfg.get("prompt_version", registry.prompt_version)
        registry.top_k = int(cfg.get("top_k", registry.top_k))
        registry.max_chunk_chars = int(
            cfg.get("max_chunk_chars", registry.max_chunk_chars)
        )
        registry.simulated_tasks_enabled = bool(
            cfg.get("simulated_tasks", registry.simulated_tasks_enabled)
        )
        if isinstance(cfg.get("prices"), dict):
            registry.prices = cfg["prices"]

        personas_cfg = cfg.get("personas", {}) or {}
        for pid, override in personas_cfg.items():
            base = registry.personas.get(pid)
            if base is None:
                logger.warning("YAML overrides unknown persona %r; ignoring.", pid)
                continue
            if not isinstance(override, dict):
                continue
            base.enabled = bool(override.get("enabled", base.enabled))
            base.weight = float(override.get("weight", base.weight))
            base.interests = override.get("interests", base.interests)
            base.simulated_task = override.get(
                "simulated_task", base.simulated_task
            )
            if "prompt_file" in override:
                base.prompt_template = _load_prompt(override["prompt_file"])
            elif "prompt_inline" in override:
                base.prompt_template = override["prompt_inline"]
            registry.weights[pid] = base.weight

    return registry


_BUILTIN_IDS: tuple[str, ...] = tuple(row[0] for row in _BUILTIN)
