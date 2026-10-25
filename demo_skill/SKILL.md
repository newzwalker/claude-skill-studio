---
name: mcp-schema-auditor
description: "Audit MCP server JSON schemas and validate tool contracts. Use when debugging or testing MCP servers and Claude Code tools."
---

# Mcp Schema Auditor

Audit MCP server JSON schemas and validate tool contracts

## When to Use (Trigger Conditions)

- **Activate when:** debugging or testing MCP servers and Claude Code tools
- **Do NOT activate when:** performing unrelated general coding tasks.

## Step-by-Step Workflow

1. **Inspect Context & Inputs**: Verify target files and environment prerequisites before executing changes.
2. **Execute Core Task**: Follow minimal, deterministic operations with explicit validation.
3. **Verify Output**: Run the verification check below and confirm zero errors before reporting completion.

```bash
claude-skill-studio lint SKILL.md
```

## Error Handling & Edge Cases

- If required dependencies or inputs are missing, surface a clear diagnostic message rather than guessing parameters.
