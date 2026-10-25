"""Command-line interface for claude-skill-studio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .linter import audit_skill_directory, scaffold_skill_markdown


def _print_report(rep) -> None:
    badge = "PASS (ANTHROPIC GUIDE COMPLIANT)" if rep.passed else "FAIL / NEEDS FIXES"
    print("=" * 72)
    print(f" Claude Skill Studio v0.3.0 | {badge}")
    print("=" * 72)
    print(f" Target           : {rep.target}")
    print(f" Skill Name       : {rep.skill_name}")
    print(f" Compliance Score : {rep.score:.1f} / 100.0  [Grade: {rep.grade}]")
    print(f" Level-1 Metadata : ~{rep.level1_frontmatter_tokens} tokens (Always loaded in system prompt)")
    print(f" Level-2 Body     : ~{rep.level2_body_tokens} tokens ({rep.level2_line_count} lines)")
    print(f" Trigger Clause   : {'Yes' if rep.has_trigger_clause else 'Missing'} | Negative Triggers: {'Yes' if rep.has_negative_triggers else 'No'}")
    if rep.referenced_files:
        print(f" Level-3 Links    : {', '.join(rep.referenced_files)}")
    print("-" * 72)
    print(" Rule Audit Breakdown:")
    for issue in rep.issues:
        icon = "[OK]" if issue.severity == "PASS" else ("[ERR]" if issue.severity == "ERROR" else "[WARN]")
        print(f"  {icon} [{issue.rule_id}] ({issue.severity}): {issue.message}")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claude-skill-studio",
        description="Lint, profile, and scaffold Claude SKILL.md packages using Anthropic's Official Skill Guide.",
    )
    sub = parser.add_subparsers(dest="cmd")

    lint_p = sub.add_parser("lint", help="Audit a SKILL.md file or skill folder")
    lint_p.add_argument("path", help="Path to SKILL.md or skill directory")
    lint_p.add_argument("--json", action="store_true", help="Output JSON report")

    init_p = sub.add_parser("scaffold", help="Generate a new Anthropic-compliant SKILL.md")
    init_p.add_argument("--name", required=True, help="Kebab-case skill name (e.g. api-contract-tester)")
    init_p.add_argument("--what", required=True, help="What the skill does")
    init_p.add_argument("--when", required=True, help="When Claude should activate this skill")
    init_p.add_argument("--out", default="SKILL.md", help="Output SKILL.md path")

    args = parser.parse_args(argv)

    if args.cmd == "lint":
        rep = audit_skill_directory(args.path)
        if args.json:
            print(rep.to_json())
        else:
            _print_report(rep)
        return 0 if rep.passed else 1

    if args.cmd == "scaffold":
        md = scaffold_skill_markdown(args.name, args.what, args.when, include_scripts=False)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"Created Anthropic-compliant skill at: {out_path}")
        rep = audit_skill_directory(out_path)
        _print_report(rep)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
