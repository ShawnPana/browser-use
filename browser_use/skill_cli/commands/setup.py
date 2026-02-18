"""Setup command - configure browser-use for first-time use.

Handles dependency installation and configuration with mode-based
setup (local/remote/full) and optional automatic fixes.

Delegates all health checks to skill_cli/checks.py.
"""

import logging
from typing import Any, Literal

from browser_use.skill_cli.checks import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

COMMANDS = {'setup'}


async def handle(
	action: str,
	params: dict[str, Any],
) -> dict[str, Any]:
	"""Handle setup command."""
	assert action == 'setup'

	mode: Literal['local', 'remote', 'full'] = params.get('mode', 'local')
	yes: bool = params.get('yes', False)
	api_key: str | None = params.get('api_key')
	json_output: bool = params.get('json', False)

	# Validate mode
	if mode not in ('local', 'remote', 'full'):
		return {'error': f'Invalid mode: {mode}. Must be local, remote, or full'}

	# Run setup flow
	try:
		checks = await run_checks(mode)

		if not json_output:
			_log_checks(checks)

		# Plan actions
		actions = plan_actions(checks, mode, yes, api_key)

		if not json_output:
			_log_actions(actions)

		# Execute actions
		await execute_actions(actions, mode, api_key, json_output)

		# Validate
		validation = await validate_setup(mode)

		if not json_output:
			_log_validation(validation)

		return {
			'status': 'success',
			'mode': mode,
			'checks': {r.name: r.model_dump() for r in checks},
			'validation': {r.name: r.model_dump() for r in validation},
		}

	except Exception as e:
		logger.exception(f'Setup failed: {e}')
		error_msg = str(e)
		if json_output:
			return {'error': error_msg}
		return {'error': error_msg}


async def run_checks(mode: Literal['local', 'remote', 'full']) -> list[CheckResult]:
	"""Run pre-flight checks for the given setup mode.

	Delegates to checks.run_checks() with mode filtering.
	"""
	from browser_use.skill_cli.checks import run_checks as _run_checks

	return await _run_checks(mode=mode)


def plan_actions(
	checks: list[CheckResult],
	mode: Literal['local', 'remote', 'full'],
	yes: bool,
	api_key: str | None,
) -> list[dict[str, Any]]:
	"""Plan which actions to take based on checks.

	Returns:
		List of actions to execute
	"""
	actions: list[dict[str, Any]] = []

	# Build a lookup by check name
	by_name = {r.name: r for r in checks}

	# Browser installation (local/full)
	if mode in ('local', 'full'):
		browser_check = by_name.get('browser')
		if browser_check and browser_check.status != CheckStatus.OK:
			actions.append(
				{
					'type': 'install_browser',
					'description': 'Install browser (Chromium)',
					'required': True,
				}
			)

	# API key configuration (remote/full)
	# Always plan configure_api_key when --api-key is provided (fixes overwrite bug)
	if mode in ('remote', 'full'):
		if api_key:
			actions.append(
				{
					'type': 'configure_api_key',
					'description': 'Configure API key',
					'required': True,
					'api_key': api_key,
				}
			)
		else:
			api_check = by_name.get('api_key')
			if api_check and api_check.status != CheckStatus.OK:
				if not yes:
					actions.append(
						{
							'type': 'prompt_api_key',
							'description': 'Prompt for API key',
							'required': False,
						}
					)

	# Cloudflared (remote/full)
	if mode in ('remote', 'full'):
		cloudflared_check = by_name.get('cloudflared')
		if cloudflared_check and cloudflared_check.status != CheckStatus.OK:
			actions.append(
				{
					'type': 'install_cloudflared',
					'description': 'Install cloudflared (for tunneling)',
					'required': True,
				}
			)

	return actions


async def execute_actions(
	actions: list[dict[str, Any]],
	mode: Literal['local', 'remote', 'full'],
	api_key: str | None,
	json_output: bool,
) -> None:
	"""Execute planned actions.

	Args:
		actions: List of actions to execute
		mode: Setup mode (local/remote/full)
		api_key: Optional API key to configure
		json_output: Whether to output JSON
	"""
	for action in actions:
		action_type = action['type']

		if action_type == 'install_browser':
			if not json_output:
				print('📦 Installing Chromium browser (~300MB)...')
			# Browser will be installed on first use by Playwright
			if not json_output:
				print('✓ Browser available (will be installed on first use)')

		elif action_type == 'configure_api_key':
			if not json_output:
				print('🔑 Configuring API key...')
			from browser_use.skill_cli.api_key import save_api_key

			if api_key:
				save_api_key(api_key)
				if not json_output:
					print('✓ API key configured')

		elif action_type == 'prompt_api_key':
			if not json_output:
				print('🔑 API key not configured')
				print('   Set via: export BROWSER_USE_API_KEY=your_key')
				print('   Or: browser-use setup --api-key <key>')

		elif action_type == 'install_cloudflared':
			if not json_output:
				print('⚠ cloudflared not installed')
				print('   Install via:')
				print('   macOS:   brew install cloudflared')
				print(
					'   Linux:   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/.local/bin/cloudflared && chmod +x ~/.local/bin/cloudflared'
				)
				print('   Windows: winget install Cloudflare.cloudflared')
				print()
				print('   Or re-run install.sh which installs cloudflared automatically.')


async def validate_setup(
	mode: Literal['local', 'remote', 'full'],
) -> list[CheckResult]:
	"""Validate that setup worked by re-running relevant checks.

	Returns:
		List of CheckResult from re-running checks
	"""
	from browser_use.skill_cli.checks import run_checks as _run_checks

	return await _run_checks(mode=mode)


def _log_checks(checks: list[CheckResult]) -> None:
	"""Log check results."""
	print('\n✓ Running checks...\n')
	for check in checks:
		icon = '✓' if check.status == CheckStatus.OK else '⚠' if check.status == CheckStatus.WARNING else '✗'
		print(f'  {icon} {check.name.replace("_", " ")}: {check.message}')
		if check.fix:
			print(f'      Fix: {check.fix}')
	print()


def _log_actions(actions: list[dict[str, Any]]) -> None:
	"""Log planned actions."""
	if not actions:
		print('✓ No additional setup needed!\n')
		return

	print('\n📋 Setup actions:\n')
	for i, action in enumerate(actions, 1):
		required = '(required)' if action.get('required') else '(optional)'
		print(f'  {i}. {action["description"]} {required}')
	print()


def _log_validation(validation: list[CheckResult]) -> None:
	"""Log validation results."""
	print('\n✓ Validation:\n')
	for check in validation:
		icon = '✓' if check.status == CheckStatus.OK else '✗'
		print(f'  {icon} {check.name.replace("_", " ")}: {check.message}')
	print()
