"""Deterministic test suite for claude-skill-studio."""

from pathlib import Path
import tempfile

from claude_skill_studio.linter import audit_skill_markdown, scaffold_skill_markdown
from claude_skill_studio.cli import main


def test_scaffolded_skill_scores_100_grade_a():
    md = scaffold_skill_markdown(
        name="mcp-schema-validator",
        what_it_does="Validate MCP server JSON schemas, tool input signatures, and transport error codes",
        trigger_phrases="the user asks to build, debug, or validate an MCP server or tool schema",
        negative_triggers="general REST API documentation",
        include_scripts=False,
    )
    report = audit_skill_markdown(md)
    assert report.score == 100.0
    assert report.grade == "A"
    assert report.passed is True
    assert report.has_trigger_clause is True
    assert report.has_negative_triggers is True


def test_bad_skill_catches_xml_injection_and_bad_name():
    bad_md = """---
name: Invalid_Skill Name!
description: A vague description with <script>alert(1)</script> XML tags and no trigger clause.
---
Too short.
"""
    report = audit_skill_markdown(bad_md)
    assert report.passed is False
    assert report.grade == "F"
    rule_ids = {i.rule_id for i in report.issues if i.severity in ("ERROR", "WARN")}
    assert "ANT-NAME-002" in rule_ids
    assert "ANT-SEC-001" in rule_ids
    assert "ANT-DESC-002" in rule_ids


def test_cli_scaffold_and_lint_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / "SKILL.md"
        code1 = main(
            [
                "scaffold",
                "--name",
                "claude-pr-auditor",
                "--what",
                "Run deterministic security and diff checks on pull requests",
                "--when",
                "reviewing a PR or auditing git diffs before merge",
                "--out",
                str(out_file),
            ]
        )
        assert code1 == 0
        assert out_file.exists()

        code2 = main(["lint", str(out_file)])
        assert code2 == 0


if __name__ == "__main__":
    test_scaffolded_skill_scores_100_grade_a()
    test_bad_skill_catches_xml_injection_and_bad_name()
    test_cli_scaffold_and_lint_roundtrip()
    print("ALL CLAUDE SKILL STUDIO TESTS PASSED!")
