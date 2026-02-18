"""Tests for setup command.

These tests call real functions without mocking. They verify the
structure and logic of the setup command against actual system state.
"""

from browser_use.skill_cli.checks import CheckResult, CheckStatus
from browser_use.skill_cli.commands import setup


async def test_setup_local_mode():
	"""Test setup with local mode runs without error."""
	result = await setup.handle(
		'setup',
		{
			'mode': 'local',
			'api_key': None,
			'yes': True,
			'json': True,
		},
	)

	# Should return a dict with expected structure
	assert isinstance(result, dict)
	# Either success or error, but should have a response
	assert 'status' in result or 'error' in result

	if 'status' in result:
		assert result['status'] == 'success'
		assert result['mode'] == 'local'
		assert 'checks' in result
		assert 'validation' in result


async def test_setup_remote_mode():
	"""Test setup with remote mode runs without error."""
	result = await setup.handle(
		'setup',
		{
			'mode': 'remote',
			'api_key': None,
			'yes': True,
			'json': True,
		},
	)

	# Should return a dict with expected structure
	assert isinstance(result, dict)
	assert 'status' in result or 'error' in result

	if 'status' in result:
		assert result['status'] == 'success'
		assert result['mode'] == 'remote'
		assert 'checks' in result
		assert 'validation' in result


async def test_setup_full_mode():
	"""Test setup with full mode runs without error."""
	result = await setup.handle(
		'setup',
		{
			'mode': 'full',
			'api_key': None,
			'yes': True,
			'json': True,
		},
	)

	assert isinstance(result, dict)
	assert 'status' in result or 'error' in result

	if 'status' in result:
		assert result['status'] == 'success'
		assert result['mode'] == 'full'


async def test_setup_invalid_mode():
	"""Test setup with invalid mode returns error."""
	result = await setup.handle(
		'setup',
		{
			'mode': 'invalid',
			'api_key': None,
			'yes': False,
			'json': False,
		},
	)

	assert 'error' in result
	assert 'Invalid mode' in result['error']


async def test_run_checks_local():
	"""Test run_checks returns CheckResult list for local mode."""
	checks = await setup.run_checks('local')

	assert isinstance(checks, list)
	assert all(isinstance(c, CheckResult) for c in checks)

	names = [c.name for c in checks]
	# Local mode should check package and browser
	assert 'package' in names
	assert 'browser' in names

	# Local mode should NOT check api_key or cloudflared
	assert 'api_key' not in names
	assert 'cloudflared' not in names


async def test_run_checks_remote():
	"""Test run_checks returns CheckResult list for remote mode."""
	checks = await setup.run_checks('remote')

	assert isinstance(checks, list)
	names = [c.name for c in checks]

	# Remote mode should check api_key and cloudflared
	assert 'package' in names
	assert 'api_key' in names
	assert 'cloudflared' in names

	# Remote mode should NOT check browser
	assert 'browser' not in names


async def test_run_checks_full():
	"""Test run_checks returns CheckResult list for full mode."""
	checks = await setup.run_checks('full')

	assert isinstance(checks, list)
	names = [c.name for c in checks]

	# Full mode should check everything
	assert 'package' in names
	assert 'browser' in names
	assert 'api_key' in names
	assert 'cloudflared' in names


def test_plan_actions_no_actions_needed():
	"""Test plan_actions when everything is ok."""
	checks = [
		CheckResult(name='package', status=CheckStatus.OK, message='ok'),
		CheckResult(name='browser', status=CheckStatus.OK, message='ok'),
		CheckResult(name='api_key', status=CheckStatus.OK, message='ok'),
		CheckResult(name='cloudflared', status=CheckStatus.OK, message='ok'),
	]

	actions = setup.plan_actions(checks, 'local', yes=False, api_key=None)
	assert actions == []


def test_plan_actions_install_browser():
	"""Test plan_actions when browser needs installation."""
	checks = [
		CheckResult(name='package', status=CheckStatus.OK, message='ok'),
		CheckResult(name='browser', status=CheckStatus.ERROR, message='not found'),
	]

	actions = setup.plan_actions(checks, 'local', yes=False, api_key=None)
	assert any(a['type'] == 'install_browser' for a in actions)


def test_plan_actions_configure_api_key():
	"""Test plan_actions when API key is provided."""
	checks = [
		CheckResult(name='api_key', status=CheckStatus.ERROR, message='missing'),
	]

	actions = setup.plan_actions(checks, 'remote', yes=True, api_key='test_key')
	assert any(a['type'] == 'configure_api_key' for a in actions)


def test_plan_actions_always_saves_provided_api_key():
	"""Test plan_actions always plans configure_api_key when --api-key is provided,
	even if the existing key is already ok (fixes overwrite bug)."""
	checks = [
		CheckResult(name='api_key', status=CheckStatus.OK, message='configured'),
	]

	actions = setup.plan_actions(checks, 'remote', yes=True, api_key='new_key')
	assert any(a['type'] == 'configure_api_key' for a in actions)


def test_plan_actions_prompt_api_key():
	"""Test plan_actions prompts for API key when missing and not --yes."""
	checks = [
		CheckResult(name='api_key', status=CheckStatus.ERROR, message='missing'),
	]

	actions = setup.plan_actions(checks, 'remote', yes=False, api_key=None)
	assert any(a['type'] == 'prompt_api_key' for a in actions)


def test_plan_actions_install_cloudflared():
	"""Test plan_actions when cloudflared is missing."""
	checks = [
		CheckResult(name='cloudflared', status=CheckStatus.WARNING, message='not installed'),
	]

	actions = setup.plan_actions(checks, 'remote', yes=True, api_key=None)
	assert any(a['type'] == 'install_cloudflared' for a in actions)


async def test_validate_setup_local():
	"""Test validate_setup returns CheckResult list for local mode."""
	results = await setup.validate_setup('local')

	assert isinstance(results, list)
	assert all(isinstance(r, CheckResult) for r in results)
	names = [r.name for r in results]
	assert 'package' in names
	assert 'browser' in names


async def test_validate_setup_remote():
	"""Test validate_setup returns CheckResult list for remote mode."""
	results = await setup.validate_setup('remote')

	assert isinstance(results, list)
	assert all(isinstance(r, CheckResult) for r in results)
	names = [r.name for r in results]
	assert 'package' in names
	assert 'api_key' in names
	assert 'cloudflared' in names
