"""Built-in code review prompt template for multi-model reviews."""

CODE_REVIEW_TEMPLATE = """\
# Code Review: {task_id}

You are performing an independent code review. You did NOT write this code —
you are coming in cold with fresh context. Your job is to evaluate the
implementation against the plan and acceptance criteria, surface issues,
and provide a clear verdict.

## Context

### Task
**ID:** {task_id}

### Task Description
{task_description}

### Plan
{plan_content}

### Project Context
{project_context}

### Diff
```
{diff_content}
```

## Review Checklist

Evaluate the diff against each category. For every issue found, state the
file, line number, severity (critical / major / minor), and a concrete fix.

### Correctness
- Does the implementation match the plan and acceptance criteria?
- Are there logic errors, off-by-one errors, or missing edge cases?
- Are error paths handled correctly?
- Are return values and types correct?
- Are all branches reachable and necessary?

### Security
- Any injection vectors (command injection, SQL injection, XSS, path traversal)?
- Secrets or credentials exposed or logged?
- Input validation at system boundaries?
- Unsafe deserialization or file operations?

### Quality
- Does the code follow existing patterns and conventions in this codebase?
- Are names clear, consistent, and idiomatic?
- Is complexity appropriate — no over-engineering, no under-engineering?
- Is the code readable without excessive comments?
- Are imports, dependencies, and module boundaries clean?

### Testing
- Are changes covered by tests?
- Do tests verify behavior, not implementation details?
- Are edge cases and error paths tested?
- Are test names descriptive of what they verify?

### Performance
- Any obvious performance issues (N+1 queries, unbounded loops, unnecessary allocations)?
- Are there concurrency concerns (race conditions, deadlocks)?
- Are resources properly cleaned up (file handles, connections)?

## Output Format

Write your review as a structured markdown document with these sections:

### 1. Verdict

One of:
- **PASS** — Implementation is correct and meets acceptance criteria.
- **FAIL (implementation-level)** — Plan is sound but implementation has issues that need fixing. The task should return to `in_progress` for rework.
- **FAIL (plan-level)** — The approach itself is flawed. The task should return to `in_planning` for a revised plan.

### 2. Summary

2-3 sentences: what was reviewed, what the overall quality is, and the key finding (if any).

### 3. Issues

Ordered by severity (critical first). For each issue:

```
**[SEVERITY] file:line — Short description**
Description of the problem and why it matters.
**Fix:** Concrete suggestion for how to resolve it.
```

If no issues found, write "No issues found."

### 4. Positive Observations

What was done well. This keeps reviews balanced and acknowledges good work.
Mention specific patterns, test coverage, or design decisions that are noteworthy.

---

Write your review to: {output_path}
"""
