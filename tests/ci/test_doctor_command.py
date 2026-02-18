"""Tests for doctor command and checks module."""

import tempfile

import pytest

from browser_use.skill_cli.checks import CheckResult, CheckStatus, check_browser, check_cloudflared, check_network, check_package, check_server_staleness, run_checks
from browser_use.skill_cli.commands import doctor


@pytest.mark.asyncio
async def test_doctor_handle_returns_valid_structure():
	"""Test that doctor.handle() returns a valid result structure."""
	result = await doctor.handle()

	# Verify structure
	assert 'status' in result
	assert result['status'] in ('healthy', 'issues_found')
	assert 'checks' in result
	assert 'summary' in result

	# Verify checks are present (at least package and network always run)
	checks = result['checks']
	assert 'package' in checks
	assert 'network' in checks
	for check in checks.values():
		assert 'status' in check
		assert 'message' in check


def test_check_package_installed():
	"""Test check_package returns ok when browser-use is installed."""
	result = check_package()
	assert isinstance(result, CheckResult)
	assert result.status == CheckStatus.OK
	assert 'browser-use' in result.message


def test_check_browser_returns_valid_structure():
	"""Test check_browser returns a valid CheckResult."""
	result = check_browser()
	assert isinstance(result, CheckResult)
	assert result.name == 'browser'
	assert result.status in (CheckStatus.OK, CheckStatus.WARNING, CheckStatus.ERROR)


@pytest.mark.asyncio
async def test_check_api_key_with_env_var(monkeypatch):
	"""Test check_api_key_valid when API key is set via env var."""
	from browser_use.skill_cli.checks import check_api_key_valid

	monkeypatch.setenv('BROWSER_USE_API_KEY', 'test_key_12345')

	result = await check_api_key_valid()
	assert isinstance(result, CheckResult)
	# Key is present (may or may not validate against real API)
	assert result.name == 'api_key'
	assert result.details.get('source') == 'env'


@pytest.mark.asyncio
async def test_check_api_key_missing(monkeypatch):
	"""Test check_api_key_valid when API key is not available."""
	from browser_use.skill_cli.checks import check_api_key_valid

	monkeypatch.delenv('BROWSER_USE_API_KEY', raising=False)

	with tempfile.TemporaryDirectory() as tmpdir:
		monkeypatch.setenv('XDG_CONFIG_HOME', tmpdir)
		monkeypatch.setenv('HOME', tmpdir)

		result = await check_api_key_valid()
		assert isinstance(result, CheckResult)
		assert result.status == CheckStatus.ERROR
		assert result.fix is not None
		assert 'browser-use setup' in result.fix


def test_check_cloudflared_returns_valid_structure():
	"""Test check_cloudflared returns a valid CheckResult."""
	result = check_cloudflared()
	assert isinstance(result, CheckResult)
	assert result.name == 'cloudflared'
	assert result.status in (CheckStatus.OK, CheckStatus.WARNING)


@pytest.mark.asyncio
async def test_check_network_returns_valid_structure():
	"""Test check_network returns a valid CheckResult."""
	result = await check_network()
	assert isinstance(result, CheckResult)
	assert result.name == 'network'
	assert result.status in (CheckStatus.OK, CheckStatus.WARNING)


def test_summarize_results_all_ok():
	"""Test _summarize_results when all checks pass."""
	results = [
		CheckResult(name='a', status=CheckStatus.OK, message='ok'),
		CheckResult(name='b', status=CheckStatus.OK, message='ok'),
		CheckResult(name='c', status=CheckStatus.OK, message='ok'),
	]
	summary = doctor._summarize_results(results)
	assert '3/3' in summary


def test_summarize_results_mixed():
	"""Test _summarize_results with mixed results."""
	results = [
		CheckResult(name='a', status=CheckStatus.OK, message='ok'),
		CheckResult(name='b', status=CheckStatus.WARNING, message='warn'),
		CheckResult(name='c', status=CheckStatus.ERROR, message='err'),
	]
	summary = doctor._summarize_results(results)
	assert '1/3' in summary
	assert '1 warning' in summary
	assert '1 error' in summary


@pytest.mark.asyncio
async def test_run_checks_returns_check_results():
	"""Test run_checks returns list of CheckResult."""
	results = await run_checks()
	assert isinstance(results, list)
	assert all(isinstance(r, CheckResult) for r in results)
	# At least package and network always present
	names = [r.name for r in results]
	assert 'package' in names
	assert 'network' in names


def test_check_server_staleness_no_meta():
	"""Test check_server_staleness with no .meta file."""
	result = check_server_staleness('nonexistent_session_xyz', 'chromium', False, None)
	assert result.status == CheckStatus.OK


def test_check_server_staleness_matching_config():
	"""Test check_server_staleness when config matches."""
	import json
	from pathlib import Path

	session = 'test_staleness_match'
	meta_path = Path(tempfile.gettempdir()) / f'browser-use-{session}.meta'
	try:
		meta_path.write_text(json.dumps({
			'browser_mode': 'chromium',
			'headed': False,
			'profile': None,
		}))
		result = check_server_staleness(session, 'chromium', False, None)
		assert result.status == CheckStatus.OK
	finally:
		meta_path.unlink(missing_ok=True)


def test_check_server_staleness_detects_mode_change():
	"""Test check_server_staleness detects browser mode change."""
	import json
	from pathlib import Path

	session = 'test_staleness_mode'
	meta_path = Path(tempfile.gettempdir()) / f'browser-use-{session}.meta'
	try:
		meta_path.write_text(json.dumps({
			'browser_mode': 'chromium',
			'headed': False,
			'profile': None,
		}))
		result = check_server_staleness(session, 'remote', False, None)
		assert result.status == CheckStatus.WARNING
		assert 'browser_mode' in result.details['changed']
	finally:
		meta_path.unlink(missing_ok=True)


def test_check_server_staleness_detects_headed_change():
	"""Test check_server_staleness detects headed flag change."""
	import json
	from pathlib import Path

	session = 'test_staleness_headed'
	meta_path = Path(tempfile.gettempdir()) / f'browser-use-{session}.meta'
	try:
		meta_path.write_text(json.dumps({
			'browser_mode': 'chromium',
			'headed': False,
			'profile': None,
		}))
		result = check_server_staleness(session, 'chromium', True, None)
		assert result.status == CheckStatus.WARNING
		assert 'headed' in result.details['changed']
	finally:
		meta_path.unlink(missing_ok=True)
