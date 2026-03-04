"""Built-in plan review prompt template for multi-model reviews."""

PLAN_REVIEW_TEMPLATE = """\
# Plan Review: {task_id}

You are reviewing a plan before implementation begins. Your job is to evaluate
whether this plan is complete, feasible, and aligned with the task description.
Catching plan-level issues now is far cheaper than discovering them during
code review.

## Context

### Task
**ID:** {task_id}

### Task Description
{task_description}

### Plan
{plan_content}

### Project Context
{project_context}

## Review Checklist

Evaluate the plan against each category. For every issue found, state the
section of the plan, severity (critical / major / minor), and a concrete
recommendation.

### Completeness
- Does the plan address every requirement in the task description?
- Are all acceptance criteria covered by the proposed approach?
- Are there implicit requirements (error handling, logging, documentation) that the plan should address?
- Does the plan identify which files will be created or modified?

### Feasibility
- Is the proposed approach technically sound?
- Are there known limitations, library constraints, or API restrictions that would block the approach?
- Is the scope realistic for a single implementation pass?
- Are the proposed changes compatible with the existing codebase architecture?

### Alignment
- Does the plan solve what the task description asks for — not more, not less?
- Are there any scope creep risks (unnecessary features, premature abstractions)?
- Does the plan respect existing patterns and conventions in the codebase?

### Risk Identification
- What could go wrong during implementation?
- Are there edge cases the plan doesn't address?
- Are there dependency risks (other tasks, external services, data migrations)?
- Does the plan identify any breaking changes or backward-compatibility concerns?

### Acceptance Criteria Coverage
- For each acceptance criterion in the task description, is there a clear corresponding step in the plan?
- Are the criteria testable and verifiable?
- Are there missing acceptance criteria that should be added?

### Architectural Concerns
- Does the plan introduce new patterns that diverge from existing conventions?
- Are module boundaries and layer separations respected?
- Will the proposed changes create technical debt?
- Are there simpler alternatives that achieve the same goal?

## Output Format

Write your review as a structured markdown document with these sections:

### 1. Verdict

One of:
- **PASS** — Plan is complete, feasible, and aligned. Implementation can proceed.
- **FAIL (plan-level)** — Plan has significant gaps or issues that need to be addressed before implementation. The task should return to `in_planning` for revision.

### 2. Summary

2-3 sentences: what was reviewed, overall assessment of plan quality, and the key concern (if any).

### 3. Issues

Ordered by severity (critical first). For each issue:

```
**[SEVERITY] Plan section — Short description**
Description of the concern and why it matters.
**Recommendation:** Concrete suggestion for how to improve the plan.
```

If no issues found, write "No issues found."

### 4. Positive Observations

What the plan does well — clarity, thoroughness, good decomposition, risk awareness.
Acknowledge strong planning to reinforce the practice.

---

Write your review to: {output_path}
"""
