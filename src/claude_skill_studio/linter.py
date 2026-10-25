"""
Anthropic Official Skill Guide Linter & Progressive Disclosure Profiler.

Enforces the architectural rules from Anthropic's 'The Complete Guide to Building Skills for Claude':
1. Strict kebab-case `name` and trigger-rich `description` ("Use when...") in YAML frontmatter.
2. Security checks: no XML brackets (< or >) in frontmatter, no reserved 'claude-'/'anthropic-' prefix abuse.
3. 3-Level Progressive Disclosure:
   - Level 1 (YAML Frontmatter): <= 80 tokens (~300 chars) always loaded in system prompt.
   - Level 2 (SKILL.md Body): <= 500 lines / ~2,500 tokens loaded on skill activation.
   - Level 3 (Bundled Resources): `scripts/`, `references/`, `assets/` linked on demand.
4. Actionable workflow steps, error-handling guidance, and trigger test cases.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class SkillIssue:
    rule_id: str
    severity: str  # "ERROR", "WARN", "PASS"
    message: str
    penalty: float = 0.0


@dataclass
class SkillAuditReport:
    target: str
    skill_name: str
    score: float
    grade: str
    passed: bool
    level1_frontmatter_tokens: int
    level2_body_tokens: int
    level2_line_count: int
    has_trigger_clause: bool
    has_negative_triggers: bool
    referenced_files: List[str]
    issues: List[SkillIssue] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def _estimate_tokens(text: str) -> int:
    """Fast deterministic token approximation (~4 chars per token + word boundary weighting)."""
    words = len(re.findall(r"\S+", text))
    chars = len(text)
    return max(1, int(round((words * 1.3 + chars / 4.0) / 2.0)))


def _parse_frontmatter(md_text: str) -> Tuple[Optional[Dict[str, str]], str, str]:
    """Extract YAML frontmatter dictionary, raw YAML string, and markdown body."""
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "", md_text

    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx == -1:
        return None, "", md_text

    raw_yaml = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])

    meta: Dict[str, str] = {}
    current_key: Optional[str] = None
    for line in lines[1:end_idx]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            current_key = k.strip()
            meta[current_key] = v.strip().strip('"').strip("'")
        elif current_key and line.startswith((" ", "\t")):
            meta[current_key] = (meta[current_key] + " " + stripped).strip()

    return meta, raw_yaml, body


def audit_skill_markdown(md_text: str, target_name: str = "SKILL.md") -> SkillAuditReport:
    """
    Validate a SKILL.md document against Anthropic's Complete Guide to Building Skills for Claude.
    """
    meta, raw_yaml, body = _parse_frontmatter(md_text)
    issues: List[SkillIssue] = []
    score = 100.0

    if meta is None:
        issues.append(
            SkillIssue(
                rule_id="ANT-FM-001",
                severity="ERROR",
                message="Missing YAML frontmatter delimited by `---` at top of SKILL.md.",
                penalty=45.0,
            )
        )
        return SkillAuditReport(
            target=target_name,
            skill_name="<missing>",
            score=55.0,
            grade="F",
            passed=False,
            level1_frontmatter_tokens=0,
            level2_body_tokens=_estimate_tokens(md_text),
            level2_line_count=len(md_text.splitlines()),
            has_trigger_clause=False,
            has_negative_triggers=False,
            referenced_files=[],
            issues=issues,
        )

    skill_name = meta.get("name", "").strip()
    description = meta.get("description", "").strip()

    # Rule 1: Valid kebab-case skill name
    if not skill_name:
        score -= 25.0
        issues.append(
            SkillIssue("ANT-NAME-001", "ERROR", "Missing required `name` field in YAML frontmatter.", 25.0)
        )
    elif not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", skill_name):
        score -= 15.0
        issues.append(
            SkillIssue(
                "ANT-NAME-002",
                "ERROR",
                f"Skill name '{skill_name}' must be strict kebab-case (lowercase alphanumeric and hyphens only).",
                15.0,
            )
        )
    else:
        issues.append(
            SkillIssue("ANT-NAME-001", "PASS", f"Valid kebab-case skill identifier: `{skill_name}`.", 0.0)
        )

    # Rule 2: Security check — no XML tags in frontmatter (Anthropic Guide Security Rule)
    if "<" in raw_yaml or ">" in raw_yaml:
        score -= 20.0
        issues.append(
            SkillIssue(
                "ANT-SEC-001",
                "ERROR",
                "YAML frontmatter contains `<` or `>` characters (prompt injection risk in Level-1 system prompt).",
                20.0,
            )
        )
    else:
        issues.append(
            SkillIssue("ANT-SEC-001", "PASS", "Frontmatter passed XML angle-bracket injection check.", 0.0)
        )

    # Rule 3: Trigger-rich description ("Use when..." / "Trigger when...")
    has_trigger = bool(
        re.search(r"\b(use when|use this skill when|trigger on|triggers when|use for)\b", description, re.I)
    )
    has_neg_trigger = bool(
        re.search(r"\b(do not use|not for|don't use|skip when)\b", description + " " + body, re.I)
    )

    if not description:
        score -= 30.0
        issues.append(
            SkillIssue("ANT-DESC-001", "ERROR", "Missing `description` field in YAML frontmatter.", 30.0)
        )
    else:
        if not has_trigger:
            score -= 15.0
            issues.append(
                SkillIssue(
                    "ANT-DESC-002",
                    "WARN",
                    "Description lacks explicit trigger conditions (e.g., 'Use when the user asks to...').",
                    15.0,
                )
            )
        else:
            issues.append(
                SkillIssue(
                    "ANT-DESC-002",
                    "PASS",
                    "Description contains explicit activation trigger phrasing ('Use when...').",
                    0.0,
                )
            )

        if len(description) > 1024:
            score -= 12.0
            issues.append(
                SkillIssue(
                    "ANT-DESC-003",
                    "ERROR",
                    f"Description exceeds Anthropic's 1,024-char limit ({len(description)} chars).",
                    12.0,
                )
            )
        elif len(description) > 350:
            score -= 5.0
            issues.append(
                SkillIssue(
                    "ANT-DESC-003",
                    "WARN",
                    f"Description is {len(description)} chars; keeping Level-1 metadata <= 300 chars preserves context budget.",
                    5.0,
                )
            )
        else:
            issues.append(
                SkillIssue(
                    "ANT-DESC-003",
                    "PASS",
                    f"Level-1 description length is compact ({len(description)} chars).",
                    0.0,
                )
            )

    # Rule 4: Progressive Disclosure Level-2 Body Size
    body_lines = [ln for ln in body.splitlines() if ln.strip()]
    total_lines = len(md_text.splitlines())
    l1_tokens = _estimate_tokens(raw_yaml)
    l2_tokens = _estimate_tokens(body)

    if total_lines > 500 or l2_tokens > 4500:
        score -= 15.0
        issues.append(
            SkillIssue(
                "ANT-PROG-001",
                "WARN",
                f"SKILL.md is {total_lines} lines (~{l2_tokens} tokens). Move bulky reference tables into `references/`.",
                15.0,
            )
        )
    elif len(body_lines) < 5:
        score -= 18.0
        issues.append(
            SkillIssue(
                "ANT-PROG-002",
                "ERROR",
                "SKILL.md body has almost no actionable workflow instructions.",
                18.0,
            )
        )
    else:
        issues.append(
            SkillIssue(
                "ANT-PROG-001",
                "PASS",
                f"Progressive Disclosure Level-2 budget healthy ({total_lines} lines, ~{l2_tokens} tokens).",
                0.0,
            )
        )

    # Rule 5: Actionable structure (headings, code blocks / examples)
    has_headings = bool(re.search(r"^#{1,3}\s+\S+", body, re.M))
    has_code_or_steps = ("```" in body) or bool(re.search(r"^\s*1\.\s+\S+", body, re.M))
    if not has_headings or not has_code_or_steps:
        score -= 10.0
        issues.append(
            SkillIssue(
                "ANT-WORK-001",
                "WARN",
                "Include structured markdown headings (`## Workflow`) and numbered steps or code examples.",
                10.0,
            )
        )
    else:
        issues.append(
            SkillIssue(
                "ANT-WORK-001",
                "PASS",
                "Body includes structured workflow headings and executable examples/steps.",
                0.0,
            )
        )

    # Discover Level-3 resource links (scripts/, references/, assets/)
    refs = sorted(
        set(
            re.findall(
                r"(?:scripts|references|assets|examples)/[A-Za-z0-9_.\-/]+",
                body,
            )
        )
    )

    final_score = round(max(0.0, min(100.0, score)), 1)
    if final_score >= 90.0:
        grade = "A"
    elif final_score >= 80.0:
        grade = "B"
    elif final_score >= 68.0:
        grade = "C"
    else:
        grade = "F"

    return SkillAuditReport(
        target=target_name,
        skill_name=skill_name or "<unnamed>",
        score=final_score,
        grade=grade,
        passed=final_score >= 80.0 and not any(i.severity == "ERROR" for i in issues),
        level1_frontmatter_tokens=l1_tokens,
        level2_body_tokens=l2_tokens,
        level2_line_count=total_lines,
        has_trigger_clause=has_trigger,
        has_negative_triggers=has_neg_trigger,
        referenced_files=refs,
        issues=issues,
    )


def audit_skill_directory(skill_dir: str | Path) -> SkillAuditReport:
    """Audit a skill folder, including verifying that linked Level-3 files exist on disk."""
    folder = Path(skill_dir)
    skill_md = folder / "SKILL.md" if folder.is_dir() else folder
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md not found at: {skill_md}")

    report = audit_skill_markdown(skill_md.read_text(encoding="utf-8"), target_name=str(skill_md))
    base_dir = skill_md.parent

    for rel_path in report.referenced_files:
        candidate = base_dir / rel_path
        if not candidate.exists():
            report.score = round(max(0.0, report.score - 10.0), 1)
            report.passed = False
            report.issues.append(
                SkillIssue(
                    rule_id="ANT-LINK-001",
                    severity="ERROR",
                    message=f"Broken Level-3 resource link: `{rel_path}` does not exist in skill folder.",
                    penalty=10.0,
                )
            )
    return report


def scaffold_skill_markdown(
    name: str,
    what_it_does: str,
    trigger_phrases: str,
    negative_triggers: str = "",
    include_scripts: bool = True,
) -> str:
    """Generate a compliant, production-ready SKILL.md following Anthropic's Official Guide."""
    clean_name = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "my-claude-skill"
    desc = f"{what_it_does.strip().rstrip('.')}. Use when {trigger_phrases.strip().rstrip('.')}."
    if negative_triggers.strip():
        desc += f" Do NOT use for {negative_triggers.strip().rstrip('.')}."

    script_section = ""
    if include_scripts:
        script_section = f"""
## Bundled Resources (Level-3 Progressive Disclosure)

- `scripts/verify_{clean_name.replace('-', '_')}.py` — Deterministic CLI verifier and self-test runner.
- `references/api-guide.md` — Detailed edge-case reference loaded only when needed.
"""

    return f"""---
name: {clean_name}
description: "{desc}"
---

# {clean_name.replace('-', ' ').title()}

{what_it_does.strip()}

## When to Use (Trigger Conditions)

- **Activate when:** {trigger_phrases.strip()}
- **Do NOT activate when:** {negative_triggers.strip() or "performing unrelated general coding tasks."}

## Step-by-Step Workflow

1. **Inspect Context & Inputs**: Verify target files and environment prerequisites before executing changes.
2. **Execute Core Task**: Follow minimal, deterministic operations with explicit validation.
3. **Verify Output**: Run the verification check below and confirm zero errors before reporting completion.

```bash
claude-skill-studio lint SKILL.md
```
{script_section}
## Error Handling & Edge Cases

- If required dependencies or inputs are missing, surface a clear diagnostic message rather than guessing parameters.
"""
