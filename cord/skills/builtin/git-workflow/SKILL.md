---
name: git-workflow
description: Professional Git version control, semantic conventional commits, branch management, status diagnostics, and repo workflows.
category: DevOps & Version Control
---

# Git Workflow & Commit Crafting Skill

Best practices for version control and clean git operations in CORD.

## Commit Guidelines
- Use conventional commits format:
  - `feat: add new feature`
  - `fix: resolve bug in module`
  - `refactor: restructure code without behavioral changes`
  - `test: add unit or integration tests`
  - `docs: update documentation or README`
- Always run `git status` and `git diff` before committing to avoid unintended staged files.
- Commit logically grouped changes together rather than giant monolithic dumps.
