---
name: test-automator
description: Automated test generation, pytest fixture creation, mocking external APIs, edge case coverage, and regression prevention.
category: Testing & QA
---

# Automated Testing & QA Skill

Instructions for creating high-coverage test suites in Python.

## Test Standards
- Write modular pytest test functions with clear descriptive names: `test_<feature>_<expected_behavior>()`.
- Use `unittest.mock.patch` or `pytest-mock` to isolate external dependencies (network requests, LLM API calls, system commands).
- Test both sunny-day (happy path) and rainy-day (exceptions, bad inputs, timeouts) scenarios.
- Run tests via `pytest tests/` and verify 100% pass rate.
