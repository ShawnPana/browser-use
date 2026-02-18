"""Health and diagnostic checks for browser-use CLI.

All health/diagnostic logic lives here. Command handlers (doctor, setup) and
main.py are thin consumers that import from this module.

Check functions wrap existing utilities into CheckResult — they do NOT
duplicate the underlying logic. The utilities remain the source of truth
for their domain; this module is the single place that interprets their
results as health diagnostics.
"""

import hashlib
import json
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
	OK = 'ok'
	WARNING = 'warning'
	ERROR = 'error'


class CheckResult(BaseModel):
	model_config = ConfigDict(extra='forbid')

	name: str
	status: CheckStatus
	message: str
	fix: str | None = None
	details: dict[str, Any] = {}


def check_package() -> CheckResult:
	"""Check if browser-use is installed."""
	try:
		import browser_use

		version = getattr(browser_use, '__version__', 'unknown')
		return CheckResult(
			name='package',
			status=CheckStatus.OK,
			message=f'browser-use {version}',
		)
	except ImportError:
		return CheckResult(
			name='package',
			status=CheckStatus.ERROR,
			message='browser-use not installed',
			fix='uv pip install browser-use',
		)


def check_browser() -> CheckResult:
	"""Check if browser is available.

	Checks both BrowserProfile import (chromium mode) and
	find_chrome_executable() (real mode).
	"""
	from browser_use.skill_cli.utils import find_chrome_executable

	details: dict[str, Any] = {}

	# Check chromium mode (BrowserProfile import)
	chromium_ok = False
	try:
		from browser_use.browser.profile import BrowserProfile

		BrowserProfile(headless=True)
		chromium_ok = True
		details['chromium'] = True
	except Exception as e:
		details['chromium'] = False
		details['chromium_error'] = str(e)

	# Check real mode (Chrome executable)
	chrome_path = find_chrome_executable()
	details['real'] = chrome_path is not None
	if chrome_path:
		details['chrome_path'] = chrome_path

	if chromium_ok:
		return CheckResult(
			name='browser',
			status=CheckStatus.OK,
			message='Browser available',
			details=details,
		)

	if chrome_path:
		return CheckResult(
			name='browser',
			status=CheckStatus.WARNING,
			message='Chromium not available, but Chrome found for real mode',
			details=details,
		)

	return CheckResult(
		name='browser',
		status=CheckStatus.ERROR,
		message='No browser available',
		fix='browser-use install',
		details=details,
	)


async def check_api_key_valid() -> CheckResult:
	"""Check API key presence and validity.

	Wraps api_key.check_api_key() for presence, then hits the API
	to verify auth (401 = invalid).
	"""
	from browser_use.skill_cli.api_key import check_api_key

	status = check_api_key()
	if not status['available']:
		return CheckResult(
			name='api_key',
			status=CheckStatus.ERROR,
			message='No API key configured',
			fix='browser-use setup --api-key <key>',
			details={'source': None, 'key_prefix': None},
		)

	details: dict[str, Any] = {
		'source': status['source'],
		'key_prefix': status['key_prefix'],
	}

	# Validate key against API
	try:
		import httpx

		from browser_use.skill_cli.api_key import get_api_key

		key = get_api_key()
		if key:
			async with httpx.AsyncClient(timeout=5.0) as client:
				response = await client.get(
					'https://api.browser-use.com/api/v2/browsers',
					headers={'Authorization': f'Bearer {key}'},
				)
				if response.status_code == 401:
					details['reason'] = 'rejected_by_api'
					return CheckResult(
						name='api_key',
						status=CheckStatus.ERROR,
						message=f'API key invalid (rejected by API, source: {status["source"]})',
						fix='browser-use setup --api-key <key>',
						details=details,
					)
	except Exception as e:
		# Network error — key is present, can't validate
		logger.debug(f'API key validation failed: {e}')
		details['validation'] = 'skipped'

	return CheckResult(
		name='api_key',
		status=CheckStatus.OK,
		message=f'API key configured ({status["source"]})',
		details=details,
	)


def check_cloudflared() -> CheckResult:
	"""Check if cloudflared is available.

	Wraps tunnel.get_tunnel_manager().get_status().
	"""
	from browser_use.skill_cli.tunnel import get_tunnel_manager

	tunnel_mgr = get_tunnel_manager()
	status_info = tunnel_mgr.get_status()

	if status_info['available']:
		return CheckResult(
			name='cloudflared',
			status=CheckStatus.OK,
			message=f'Cloudflared available ({status_info["source"]})',
			details={'path': status_info.get('path')},
		)

	return CheckResult(
		name='cloudflared',
		status=CheckStatus.WARNING,
		message='Cloudflared not installed',
		fix='brew install cloudflared (macOS) or see docs',
		details={'note': 'Will be auto-installed on first tunnel use'},
	)


async def check_network() -> CheckResult:
	"""Check basic network connectivity via HEAD to api.github.com."""
	try:
		import httpx

		async with httpx.AsyncClient(timeout=5.0) as client:
			response = await client.head('https://api.github.com', follow_redirects=True)
			if response.status_code < 500:
				return CheckResult(
					name='network',
					status=CheckStatus.OK,
					message='Network connectivity OK',
				)
	except Exception as e:
		logger.debug(f'Network check failed: {e}')

	return CheckResult(
		name='network',
		status=CheckStatus.WARNING,
		message='Network connectivity check inconclusive',
		details={'note': 'Some features may not work offline'},
	)


def _hash_api_key(key: str) -> str:
	"""Hash an API key for storage/comparison. Returns first 16 hex chars of SHA-256."""
	return hashlib.sha256(key.encode()).hexdigest()[:16]


def check_server_staleness(
	session: str,
	browser_mode: str,
	headed: bool,
	profile: str | None,
) -> CheckResult:
	"""Check if a running server's config matches the requested config.

	Reads the .meta file for the session and compares all fields
	including api_key_hash.

	Returns OK if config matches, WARNING with changed fields if stale.
	"""
	import tempfile
	from pathlib import Path

	meta_path = Path(tempfile.gettempdir()) / f'browser-use-{session}.meta'

	if not meta_path.exists():
		return CheckResult(
			name='server_staleness',
			status=CheckStatus.OK,
			message='No metadata file (new session)',
		)

	try:
		meta = json.loads(meta_path.read_text())
	except (json.JSONDecodeError, OSError):
		return CheckResult(
			name='server_staleness',
			status=CheckStatus.OK,
			message='Metadata file unreadable (treating as fresh)',
		)

	changed: list[str] = []

	# Check browser mode
	existing_mode = meta.get('browser_mode')
	if existing_mode is not None and existing_mode != browser_mode:
		changed.append('browser_mode')

	# Check headed
	existing_headed = meta.get('headed')
	if existing_headed is not None and existing_headed != headed:
		changed.append('headed')

	# Check profile
	existing_profile = meta.get('profile')
	if existing_profile is not None and existing_profile != profile:
		changed.append('profile')

	# Check api_key_hash
	existing_hash = meta.get('api_key_hash')
	if existing_hash is not None:
		from browser_use.skill_cli.api_key import get_api_key

		current_key = get_api_key()
		current_hash = _hash_api_key(current_key) if current_key else None
		if current_hash != existing_hash:
			changed.append('api_key')

	if not changed:
		return CheckResult(
			name='server_staleness',
			status=CheckStatus.OK,
			message='Session config matches',
		)

	return CheckResult(
		name='server_staleness',
		status=CheckStatus.WARNING,
		message=f'Session config changed: {", ".join(changed)}',
		details={'changed': changed},
	)


async def run_checks(mode: str | None = None) -> list[CheckResult]:
	"""Run all relevant health checks, filtered by mode.

	If mode is None, reads from install_config to determine available modes.
	Returns list of CheckResult.
	"""
	from browser_use.skill_cli.install_config import get_available_modes

	available = get_available_modes() if mode is None else [mode]

	has_local = any(m in ('chromium', 'real', 'local', 'full') for m in available)
	has_remote = any(m in ('remote', 'full') for m in available)

	# Map setup modes to actual modes
	if mode == 'local':
		has_local = True
		has_remote = False
	elif mode == 'remote':
		has_local = False
		has_remote = True
	elif mode == 'full':
		has_local = True
		has_remote = True

	results: list[CheckResult] = []

	# Always check package
	results.append(check_package())

	# Browser check if local modes available
	if has_local:
		results.append(check_browser())

	# API key + cloudflared if remote available
	if has_remote:
		results.append(await check_api_key_valid())
		results.append(check_cloudflared())

	# Always check network
	results.append(await check_network())

	return results
