"""
1Password Actions for Browser Use
Provides fill_field and toggle_page_blur actions for secure credential handling.
"""

import logging

from pydantic import BaseModel, Field

from browser_use.agent.views import ActionResult
from browser_use.browser.session import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.tools.service import Tools

logger = logging.getLogger(__name__)


class FillFieldParams(BaseModel):
	"""Parameters for fill_field action"""

	field_name: str = Field(description='Field name in the item (e.g., username, password)')
	vault_name: str | None = Field(default=None, description='1Password vault name (uses default if not specified)')
	item_name: str | None = Field(default=None, description='1Password item name (uses default if not specified)')
	element_description: str = Field(
		default='', description='Optional description of the element to fill (e.g., "username input field")'
	)


class TogglePageBlurParams(BaseModel):
	"""Parameters for toggle_page_blur action"""

	blur: bool = Field(description='True to blur the page, False to unblur')


def register_onepassword_actions(tools: Tools) -> Tools:
	"""
	Register 1Password actions with the provided tools.
	Actions will check if OnePassword() was instantiated before executing.

	Args:
		tools: The browser-use tools to register actions with

	Returns:
		The tools instance with registered actions
	"""

	@tools.registry.action(
		description='Fill a field with a value from 1Password vault. Requires OnePassword() to be initialized. vault_name and item_name are optional if defaults were set. Use this to securely fill credentials without exposing them.',
		param_model=FillFieldParams,
	)
	async def fill_field(
		params: FillFieldParams,
		browser_session: BrowserSession,
		page_extraction_llm: BaseChatModel,
	) -> ActionResult:
		"""Fill a field with value from 1Password vault"""
		try:
			# Check if OnePassword service is activated
			from browser_use.integrations.onepassword import get_service

			service = get_service()
			if service is None:
				return ActionResult(
					error='OnePassword not initialized. Please call OnePassword() before using fill_field action.',
					include_in_memory=True,
				)

			# Get vault and item names (use defaults if not provided)
			default_vault, default_item = service.get_defaults()
			vault_name = params.vault_name or default_vault
			item_name = params.item_name or default_item

			# Validate required parameters
			if not vault_name:
				return ActionResult(
					error='vault_name is required. Either specify it in fill_field or set default_vault in OnePassword().',
					include_in_memory=True,
				)
			if not item_name:
				return ActionResult(
					error='item_name is required. Either specify it in fill_field or set default_item in OnePassword().',
					include_in_memory=True,
				)

			# Resolve secret from 1Password
			reference = f'op://{vault_name}/{item_name}/{params.field_name}'
			field_value = await service.resolve_secret(reference)

			# Get current page
			page = await browser_session.must_get_current_page()

			# Find the element to fill
			element_prompt = params.element_description or f'{params.field_name} input field'
			target_field = await page.must_get_element_by_prompt(element_prompt, page_extraction_llm)

			# Fill the field
			await target_field.fill(field_value)

			return ActionResult(
				extracted_content=f'Successfully filled {params.field_name} field for {vault_name}/{item_name}',
				include_in_memory=True,
			)

		except Exception as e:
			logger.error(f'Error filling field: {e}')
			return ActionResult(
				error=f'Failed to fill {params.field_name} field: {str(e)}',
				include_in_memory=True,
			)

	@tools.registry.action(
		description='Toggle CSS blur filter on the entire page for visual security when handling sensitive information. Pass blur=true to blur, blur=false to unblur.',
		param_model=TogglePageBlurParams,
	)
	async def toggle_page_blur(
		params: TogglePageBlurParams,
		browser_session: BrowserSession,
	) -> ActionResult:
		"""Toggle page blur for visual security"""
		try:
			# Get CDP session
			cdp_session = await browser_session.get_or_create_cdp_session()

			if params.blur:
				# Apply blur
				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={
						'expression': """
							(function() {
								if (document.body.getAttribute('data-page-blurred') === 'true') {
									return 'already_blurred';
								}
								document.body.style.filter = 'blur(15px)';
								document.body.style.webkitFilter = 'blur(15px)';
								document.body.style.transition = 'filter 0.3s ease';
								document.body.setAttribute('data-page-blurred', 'true');
								return 'blurred';
							})();
						""",
						'returnByValue': True,
					},
					session_id=cdp_session.session_id,
				)

				status = result.get('result', {}).get('value', '')
				if status == 'already_blurred':
					return ActionResult(
						extracted_content='Page was already blurred',
						include_in_memory=True,
					)

				logger.info('🔒 Applied page blur')
				return ActionResult(
					extracted_content='Successfully applied CSS blur to page for visual security',
					include_in_memory=True,
				)
			else:
				# Remove blur
				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={
						'expression': """
							(function() {
								if (document.body.getAttribute('data-page-blurred') !== 'true') {
									return 'not_blurred';
								}
								document.body.style.filter = 'none';
								document.body.style.webkitFilter = 'none';
								document.body.removeAttribute('data-page-blurred');
								return 'unblurred';
							})();
						""",
						'returnByValue': True,
					},
					session_id=cdp_session.session_id,
				)

				status = result.get('result', {}).get('value', '')
				if status == 'not_blurred':
					return ActionResult(
						extracted_content='Page was not blurred',
						include_in_memory=True,
					)

				logger.info('🔓 Removed page blur')
				return ActionResult(
					extracted_content='Successfully removed CSS blur from page',
					include_in_memory=True,
				)

		except Exception as e:
			logger.error(f'Error toggling page blur: {e}')
			return ActionResult(
				error=f'Failed to toggle page blur: {str(e)}',
				include_in_memory=True,
			)

	return tools


__all__ = ['register_onepassword_actions']
