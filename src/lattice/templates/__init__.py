"""Template loading utilities for Lattice review prompts."""

from __future__ import annotations

from pathlib import Path


def load_review_template(lattice_dir: Path, review_type: str) -> str:
    """Load a review template, preferring per-board override over built-in.

    *review_type* is ``"code-review"`` or ``"plan-review"``.

    Override path: ``<lattice_dir>/templates/<review_type>.md``.
    If the override file exists, its contents are returned.
    Otherwise the built-in Python template constant is returned.

    Raises ``ValueError`` for unknown review types.
    """
    override = lattice_dir / "templates" / f"{review_type}.md"
    if override.exists():
        return override.read_text(encoding="utf-8")

    if review_type == "code-review":
        from lattice.templates.code_review_prompt import CODE_REVIEW_TEMPLATE

        return CODE_REVIEW_TEMPLATE

    if review_type == "plan-review":
        from lattice.templates.plan_review_prompt import PLAN_REVIEW_TEMPLATE

        return PLAN_REVIEW_TEMPLATE

    raise ValueError(f"Unknown review type: {review_type}")
