"""
Red team testing module for adversarial validation.

This module contains tests to validate system robustness against:
- Prompt injection attacks
- Hallucination attempts
- Edge cases and boundary conditions
"""

from .runner import RedTeamRunner, run_red_team_tests

__all__ = ["RedTeamRunner", "run_red_team_tests"]
