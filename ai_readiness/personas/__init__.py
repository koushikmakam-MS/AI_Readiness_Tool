"""Persona-based documentation evaluation for AI agents.

Multi-persona LLM judge that scores how well a repository's documentation
serves different kinds of AI coding agents (onboarding, bug-fix, deploy,
security, etc.). Personas are named after famous cartoon characters that
match each role.
"""

from ai_readiness.personas.base import (
    Dimension,
    DocChunk,
    DocFile,
    PersonaDefinition,
    PersonaResult,
    RubricScore,
)
from ai_readiness.personas.registry import (
    PersonaRegistry,
    load_persona_registry,
)

__all__ = [
    "Dimension",
    "DocChunk",
    "DocFile",
    "PersonaDefinition",
    "PersonaResult",
    "PersonaRegistry",
    "RubricScore",
    "load_persona_registry",
]
