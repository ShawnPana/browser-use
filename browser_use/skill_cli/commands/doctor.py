"""Doctor command - check installation and dependencies.

Thin wrapper around checks.run_checks(). All diagnostic logic lives
in skill_cli/checks.py; this module formats and presents results.
"""

import logging
from typing import Any

from browser_use.skill_cli.checks import CheckResult, CheckStatus, run_checks

logger = logging.getLogger(__name__)

COMMANDS = {'doctor'}


async def handle() -> dict[str, Any]:
	"""Run health checks and return results."""
	results = await run_checks()

	all_ok = all(r.status == CheckStatus.OK for r in results)

	return {
		'status': 'healthy' if all_ok else 'issues_found',
		'checks': {r.name: r.model_dump() for r in results},
		'summary': _summarize_results(results),
	}


def _summarize_results(results: list[CheckResult]) -> str:
	"""Generate a summary of check results."""
	ok = sum(1 for r in results if r.status == CheckStatus.OK)
	warning = sum(1 for r in results if r.status == CheckStatus.WARNING)
	error = sum(1 for r in results if r.status == CheckStatus.ERROR)
	total = len(results)

	parts = [f'{ok}/{total} checks passed']
	if warning > 0:
		parts.append(f'{warning} warnings')
	if error > 0:
		parts.append(f'{error} errors')

	return ', '.join(parts)
