"""Dataclasses, enums, and core types for the personas package."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Dimension(str, Enum):
    """The three rating dimensions every persona scores docs on."""

    CONTEXT_SUFFICIENCY = "context_sufficiency"
    AMBIGUITY_RISK = "ambiguity_risk"
    TOKEN_EFFICIENCY = "token_efficiency"


# Display labels used in reports.
DIMENSION_LABELS: dict[Dimension, str] = {
    Dimension.CONTEXT_SUFFICIENCY: "Context Sufficiency",
    Dimension.AMBIGUITY_RISK: "Ambiguity / Hallucination Risk",
    Dimension.TOKEN_EFFICIENCY: "Token Efficiency",
}


@dataclass
class DocFile:
    """A documentation file discovered in the repo."""

    path: Path  # absolute path on disk
    relative_path: str  # path relative to repo root (POSIX-style)
    size_bytes: int
    content_hash: str  # sha256 of raw bytes
    text: str = ""  # full text (loaded lazily)
    headings: list[str] = field(default_factory=list)


@dataclass
class DocChunk:
    """A heading-bounded chunk of a (possibly large) doc."""

    doc: DocFile
    chunk_id: str  # e.g. "<relative_path>#<heading-slug>"
    heading: str
    text: str
    content_hash: str  # sha256 of chunk text


@dataclass
class RubricScore:
    """Per-doc rubric score from one persona."""

    chunk_id: str
    relative_path: str
    scores: dict[Dimension, float]  # 1.0 - 5.0 per dimension
    justification: str = ""
    suggestions: list[str] = field(default_factory=list)

    @property
    def average(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)


@dataclass
class SimulatedTaskResult:
    """Result of asking a persona to perform a canned task using only the docs."""

    task: str
    answer: str
    score: float  # 0-10, how well the docs supported the task
    missing_info: list[str] = field(default_factory=list)


@dataclass
class PersonaResult:
    """Aggregate result for a single persona over the entire repo."""

    persona_id: str
    display_name: str
    rubric_scores: list[RubricScore] = field(default_factory=list)
    task_result: Optional[SimulatedTaskResult] = None
    docs_considered: int = 0
    docs_scored: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embedding_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error: Optional[str] = None

    @property
    def dimension_averages(self) -> dict[Dimension, float]:
        """Mean score per dimension across all scored docs (1.0-5.0)."""
        out: dict[Dimension, float] = {}
        for dim in Dimension:
            values = [
                s.scores[dim] for s in self.rubric_scores if dim in s.scores
            ]
            out[dim] = sum(values) / len(values) if values else 0.0
        return out

    @property
    def overall_score(self) -> float:
        """Persona's overall doc-readiness score on a 0-100 scale.

        Combines the rubric average (weight 0.7) with the simulated task
        score (weight 0.3) when a task result is present.
        """
        averages = self.dimension_averages
        rubric_avg = (
            sum(averages.values()) / len(averages) if averages else 0.0
        )  # 1-5 scale
        rubric_100 = (rubric_avg / 5.0) * 100.0

        if self.task_result is None:
            return round(rubric_100, 1)

        task_100 = self.task_result.score * 10.0  # task score is 0-10
        return round(rubric_100 * 0.7 + task_100 * 0.3, 1)


@dataclass
class PersonaDefinition:
    """Static configuration for one persona."""

    persona_id: str  # role-based, e.g. "onboarding"
    display_name: str  # cartoon label, e.g. "Dora the Explorer"
    role: str  # short human description, e.g. "Onboarding Agent"
    interests: str  # what kinds of docs this persona cares about
    simulated_task: str  # canned task description for stage 2
    prompt_template: str  # full persona system prompt
    weight: float = 1.0  # relative weight in overall doc-readiness score
    enabled: bool = True
