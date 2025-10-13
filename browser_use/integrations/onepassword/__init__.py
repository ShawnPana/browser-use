"""
1Password Integration for Browser Use
Provides secure credential management via 1Password Service Accounts.

Usage:
	from browser_use import OnePassword, Agent, Tools

	# Simple usage - global activation
	OnePassword(default_vault='prod-secrets')
	tools = Tools()
	agent = Agent(tools=tools)

	# Advanced usage - explicit passing with multiple vaults
	prod_op = OnePassword(
		default_vault='prod-secrets',
		default_item='X',
		validate_on_init=True
	)
	dev_op = OnePassword(
		service_account_token='dev_token',
		default_vault='dev-secrets'
	)

	tools_prod = Tools(onepassword=prod_op)
	tools_dev = Tools(onepassword=dev_op)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from .service import OnePasswordService

logger = logging.getLogger(__name__)

# Module-level singleton for global activation pattern
_onepassword_service: 'OnePasswordService | None' = None


@dataclass
class OnePassword:
	"""
	1Password integration configuration for Browser Use.

	This object stores 1Password credentials and vault configuration,
	and can be passed explicitly to Tools or activated globally.
	"""

	service_account_token: str | None = None
	default_vault: str | None = None
	default_item: str | None = None
	integration_name: str = 'Browser Use'
	integration_version: str = 'v1.0.0'
	auto_authenticate: bool = True
	validate_on_init: bool = False

	# Internal
	_service: 'OnePasswordService | None' = field(default=None, init=False, repr=False)

	def __post_init__(self):
		"""Initialize and optionally validate 1Password service."""
		global _onepassword_service

		# Try importing onepassword SDK
		try:
			from .service import OnePasswordService
		except ImportError as e:
			raise ImportError('onepassword-sdk not installed. Install with: uv pip install browser-use[onepassword]') from e

		# Get token from parameter or environment
		token = self.service_account_token or os.getenv('OP_SERVICE_ACCOUNT_TOKEN')
		if not token:
			raise ValueError(
				'OP_SERVICE_ACCOUNT_TOKEN environment variable not set. Please set it or pass service_account_token parameter.'
			)

		# Create service with configuration
		self._service = OnePasswordService(
			token=token,
			default_vault=self.default_vault,
			default_item=self.default_item,
			integration_name=self.integration_name,
			integration_version=self.integration_version,
		)

		# Store globally for automatic Tools detection
		_onepassword_service = self._service

		# Auto-authenticate if requested
		if self.auto_authenticate:
			# Run authentication synchronously
			try:
				loop = asyncio.get_event_loop()
				if loop.is_running():
					# If event loop is running, schedule authentication for later
					logger.info('✅ 1Password service activated (authentication will happen on first use)')
				else:
					# Run authentication now
					loop.run_until_complete(self._service.authenticate())
					logger.info('✅ 1Password service activated and authenticated')
			except RuntimeError:
				# No event loop, will authenticate on first use
				logger.info('✅ 1Password service activated (authentication will happen on first use)')

		# Validate if requested (requires authentication)
		if self.validate_on_init:
			if not self._service.is_authenticated():
				logger.warning('⚠️  validate_on_init=True but service not authenticated yet. Validation will happen on first use.')

		logger.info('✅ 1Password service activated')

	@property
	def service(self) -> 'OnePasswordService':
		"""Get the underlying OnePasswordService instance."""
		if self._service is None:
			raise RuntimeError('OnePassword service not initialized')
		return self._service


def get_service() -> 'OnePasswordService | None':
	"""Get the active 1Password service instance, or None if not activated."""
	return _onepassword_service


__all__ = ['OnePassword', 'get_service']
