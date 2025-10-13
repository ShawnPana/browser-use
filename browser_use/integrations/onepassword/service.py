"""
1Password Service - handles authentication and secret resolution
"""

import logging

logger = logging.getLogger(__name__)


class OnePasswordService:
	"""
	1Password service for authenticating and resolving secrets.
	Uses 1Password Service Accounts for non-interactive authentication.
	"""

	def __init__(
		self,
		token: str,
		default_vault: str | None = None,
		default_item: str | None = None,
		integration_name: str = 'Browser Use',
		integration_version: str = 'v1.0.0',
	):
		"""
		Initialize 1Password service with service account token and defaults.

		Args:
			token: 1Password service account token
			default_vault: Default vault name to use
			default_item: Default item name to use
			integration_name: Name for 1Password integration
			integration_version: Version for 1Password integration
		"""
		self.token = token
		self.default_vault = default_vault
		self.default_item = default_item
		self.integration_name = integration_name
		self.integration_version = integration_version
		self.client = None
		self._authenticated = False

	async def authenticate(self) -> bool:
		"""
		Authenticate with 1Password using service account token.

		Returns:
			bool: True if authentication successful
		"""
		try:
			from onepassword.client import Client

			logger.info('🔐 Authenticating with 1Password...')

			self.client = await Client.authenticate(
				auth=self.token, integration_name=self.integration_name, integration_version=self.integration_version
			)

			self._authenticated = True
			logger.info('✅ 1Password authentication successful')
			return True

		except Exception as e:
			logger.error(f'❌ 1Password authentication failed: {e}')
			self._authenticated = False
			return False

	def is_authenticated(self) -> bool:
		"""Check if service is authenticated."""
		return self._authenticated and self.client is not None

	async def resolve_secret(self, reference: str) -> str:
		"""
		Resolve a secret reference from 1Password.

		Args:
			reference: Secret reference in format "op://vault/item/field"

		Returns:
			str: The resolved secret value

		Raises:
			RuntimeError: If not authenticated
			Exception: If secret resolution fails
		"""
		if not self.is_authenticated():
			# Try to authenticate
			authenticated = await self.authenticate()
			if not authenticated:
				raise RuntimeError('1Password service not authenticated')

		try:
			assert self.client is not None
			secret_value = await self.client.secrets.resolve(reference)
			logger.debug(f'🔑 Resolved secret: {reference}')
			return secret_value

		except Exception as e:
			logger.error(f'❌ Failed to resolve secret {reference}: {e}')
			raise

	def get_defaults(self) -> tuple[str | None, str | None]:
		"""
		Get configured default vault and item.

		Returns:
			tuple: (default_vault, default_item)
		"""
		return self.default_vault, self.default_item
