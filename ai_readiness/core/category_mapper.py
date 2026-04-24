"""Category mapping layer — reorganizes checker outputs into AI-focused categories.

Maps atomic checks from the flat dimension checkers into 3 top-level categories:
  1. AI Onboarding (25%) — Can an AI agent quickly understand and start working?
  2. AI Coding (50%)     — Can an AI agent safely and effectively modify code?
  3. Repo Health (25%)   — Is this a well-maintained, safe repository?

Each check is mapped by (source_dimension_id, check_name) → category.
Checks not in the mapping default to their source dimension's natural category.
"""

from __future__ import annotations

from ai_readiness.core.models import CategoryScore, CheckResult, DimensionScore, Report

# ── Category definitions ──────────────────────────────────────────────

CATEGORIES = {
    "ai_onboarding": {
        "name": "AI Onboarding",
        "description": "Can an AI agent quickly understand and start working on this repo?",
        "weight": 25,
    },
    "ai_coding": {
        "name": "AI Coding",
        "description": "Can an AI agent safely and effectively write/modify code here?",
        "weight": 50,
    },
    "repo_health": {
        "name": "Repo Health",
        "description": "Is this a well-maintained, safe repository for contributions?",
        "weight": 25,
    },
}

# ── Check → Category mapping ─────────────────────────────────────────
# Key: (dimension_id, check_name_substring)
# Checks are matched by substring of check name (case-insensitive).
# If a check matches multiple rules, first match wins.

_CHECK_CATEGORY_MAP: list[tuple[str, str, str, bool]] = [
    # (dimension_id, check_name_contains, target_category, scorable)

    # --- Documentation checks ---
    ("documentation", "README exists", "ai_onboarding", True),
    ("documentation", "README key sections", "ai_onboarding", True),
    ("documentation", "Architecture", "ai_onboarding", True),
    ("documentation", "CONTRIBUTING", "ai_onboarding", True),  # Moved to onboarding per critique
    ("documentation", "CODE_OF_CONDUCT", "repo_health", True),
    ("documentation", "CHANGELOG", "repo_health", True),

    # --- Setup & Onboarding checks ---
    # Having ANY build mechanism is what matters; individual options are info-only
    ("setup_onboarding", "Single-command build", "ai_onboarding", True),  # Primary scored check
    ("setup_onboarding", "Container", "ai_onboarding", False),  # Nice-to-have, info-only
    ("setup_onboarding", "Helper scripts", "ai_onboarding", True),  # Scored — scripts are important
    ("setup_onboarding", "Environment template", "ai_onboarding", False),  # Nice-to-have, info-only

    # --- AI Config checks ---
    # "Has any AI config" is the scored check; individual tools are info-only
    ("ai_config", "Copilot instructions", "ai_onboarding", False),  # Info — covered by "Has any AI config"
    ("ai_config", "Copilot setup", "ai_onboarding", False),
    ("ai_config", "Cursor", "ai_onboarding", False),
    ("ai_config", "AGENTS.md", "ai_onboarding", False),
    ("ai_config", "CLAUDE.md", "ai_onboarding", False),
    ("ai_config", "Aider", "ai_onboarding", False),
    ("ai_config", "Has any AI config", "ai_onboarding", True),  # The one scored check

    # --- AI Code Quality (static heuristics) ---
    ("ai_code_quality", "Comment density", "ai_coding", True),
    ("ai_code_quality", "Function sizes", "ai_coding", True),
    ("ai_code_quality", "File modularity", "ai_coding", True),
    ("ai_code_quality", "Examples", "ai_onboarding", True),
    ("ai_code_quality", "Naming quality", "ai_coding", True),
    ("ai_code_quality", "Inline documentation", "ai_coding", True),

    # --- Testing ---
    ("testing", "Test files exist", "ai_coding", True),
    ("testing", "Test runner", "ai_coding", True),
    ("testing", "CI/CD", "ai_coding", True),
    ("testing", "Coverage", "ai_coding", True),

    # --- Code Quality ---
    ("code_quality", "Linter", "ai_coding", True),
    ("code_quality", "Formatter", "ai_coding", True),
    ("code_quality", "Type checking", "ai_coding", True),
    ("code_quality", ".editorconfig", "ai_coding", True),  # Moved to coding per critique
    ("code_quality", "file sizes", "ai_coding", True),

    # --- Dependency ---
    ("dependency", "Dependency manifest", "ai_onboarding", True),
    ("dependency", "Lock file", "repo_health", True),
    ("dependency", ".gitignore", "repo_health", True),

    # --- Change Safety ---
    ("change_safety", "PR template", "repo_health", True),
    ("change_safety", "Issue templates", "repo_health", True),
    ("change_safety", "Pre-commit", "repo_health", True),
    ("change_safety", "SECURITY", "repo_health", True),
    ("change_safety", ".gitignore comprehensive", "repo_health", False),  # Duplicate of dependency .gitignore

    # --- LLM Code Review (all go to AI Coding) ---
    ("llm_code_review", "Readability", "ai_coding", True),
    ("llm_code_review", "Error Handling", "ai_coding", True),
    ("llm_code_review", "Design Patterns", "ai_coding", True),
    ("llm_code_review", "Code Smells", "ai_coding", True),
    ("llm_code_review", "AI Agent Friendliness", "ai_coding", True),
    ("llm_code_review", "Maintainability", "ai_coding", True),
    ("llm_code_review", "Review Summary", "ai_coding", False),  # Info-only
]

# Default category for unmapped checks
_DEFAULT_CATEGORY_MAP = {
    "documentation": "ai_onboarding",
    "setup_onboarding": "ai_onboarding",
    "ai_config": "ai_onboarding",
    "ai_code_quality": "ai_coding",
    "testing": "ai_coding",
    "code_quality": "ai_coding",
    "dependency": "repo_health",
    "change_safety": "repo_health",
    "llm_code_review": "ai_coding",
}

# Agent name → check method keys (for target_agents scoring override)
_AGENT_CHECK_MAP = {
    "copilot": {"copilot_instructions", "copilot_setup_steps"},
    "cursor": {"cursor_config"},
    "claude": {"claude_md"},
    "aider": {"aider_config"},
    "agents_md": {"agents_md"},
}

# Check display name → method key (for matching)
_AI_CONFIG_NAME_MAP = {
    "Copilot instructions": "copilot_instructions",
    "Copilot setup steps": "copilot_setup_steps",
    "Cursor config": "cursor_config",
    "AGENTS.md": "agents_md",
    "CLAUDE.md": "claude_md",
    "Aider config": "aider_config",
    "Has any AI config": "has_any",
}


def _find_mapping(dim_id: str, check_name: str) -> tuple[str, bool]:
    """Find the category and scorable flag for a check."""
    name_lower = check_name.lower()
    for rule_dim, rule_substr, category, scorable in _CHECK_CATEGORY_MAP:
        if rule_dim == dim_id and rule_substr.lower() in name_lower:
            return category, scorable
    # Default: use dimension's natural category
    return _DEFAULT_CATEGORY_MAP.get(dim_id, "repo_health"), True


def build_categories(report: Report, target_agents: list[str] | None = None) -> list[CategoryScore]:
    """Reorganize dimension checks into 3 AI-focused categories.

    This reads all checks from report.dimensions, maps each to a category,
    and returns scored CategoryScore objects.

    If target_agents is set, AI config checks for targeted agents become
    scored (not just "Has any AI config").
    """
    # Initialize categories
    cat_checks: dict[str, list[CheckResult]] = {cid: [] for cid in CATEGORIES}
    cat_insights: dict[str, list[str]] = {cid: [] for cid in CATEGORIES}

    # Build set of targeted check methods for scoring override
    targeted_methods: set[str] | None = None
    if target_agents:
        targeted_methods = set()
        for agent in target_agents:
            agent_info = _AGENT_CHECK_MAP.get(agent.lower())
            if agent_info:
                targeted_methods.update(agent_info)

    for dim in report.dimensions:
        for check in dim.checks:
            cat_id, default_scorable = _find_mapping(dim.dimension_id, check.name)

            # Override scorable for AI config checks when target_agents is set
            scorable = default_scorable
            if dim.dimension_id == "ai_config" and targeted_methods is not None:
                check_method = _AI_CONFIG_NAME_MAP.get(check.name)
                if check_method and check_method in targeted_methods:
                    scorable = True  # Targeted agent → scored
                elif check.name == "Has any AI config":
                    scorable = False  # Replaced by individual targeted checks

            # Respect check-level scorable flag from checker (e.g. from target_agents in checker)
            if hasattr(check, 'scorable') and not check.scorable:
                scorable = False

            mapped_check = CheckResult(
                name=check.name,
                status=check.status,
                message=check.message,
                recommendation=check.recommendation,
                details=check.details,
                raw_score=check.raw_score,
                check_id=check.check_id or f"{dim.dimension_id}.{check.name}",
                scorable=scorable,
            )
            cat_checks[cat_id].append(mapped_check)

        # Collect LLM insights per category
        if dim.llm_insights:
            primary_cat = _DEFAULT_CATEGORY_MAP.get(dim.dimension_id, "repo_health")
            cat_insights[primary_cat].append(dim.llm_insights)

    # Build CategoryScore objects
    categories: list[CategoryScore] = []
    for cat_id, cat_def in CATEGORIES.items():
        cat = CategoryScore(
            category_id=cat_id,
            category_name=cat_def["name"],
            description=cat_def["description"],
            weight=cat_def["weight"],
            checks=cat_checks.get(cat_id, []),
            llm_insights="\n\n".join(cat_insights.get(cat_id, [])) or None,
        )
        categories.append(cat)

    return categories
