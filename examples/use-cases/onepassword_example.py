"""
Use Case: Securely log into a website using credentials stored in 1Password vault.
- Use fill_field action to fill in username and password fields with values retrieved from 1Password. The LLM never sees the actual credentials.
- Use toggle_page_blur action to visually obscure sensitive information on the page while filling in credentials for extra security.

**SETUP**
How to setup 1Password with Browser Use:
- Get Individual Plan for 1Password
- Go to the Home page and click "New Vault"
	- Add the credentials you need for any websites you want to log into
- Go to "Developer" tab, navigate to "Directory" and create a Service Account
- Give the service account access to the vault
- Copy the Service Account Token and set it as environment variable OP_SERVICE_ACCOUNT_TOKEN
- Install browser-use with 1Password support: uv pip install browser-use[onepassword]

Note: In this example, we assume that you created a vault named "prod-secrets" and added an item named "X" with fields "username" and "password".
"""

from browser_use import Agent, Browser, ChatOpenAI, OnePassword, Tools


async def simple_example():
	"""Simple usage: Global activation with defaults."""
	# Activate 1Password globally with default vault and item
	# This allows fill_field to work without specifying vault/item every time
	OnePassword(default_vault='prod-secrets', default_item='X')

	# Initialize tools - will automatically detect OnePassword
	tools = Tools()

	browser_session = Browser()
	llm = ChatOpenAI(model='o3')

	agent = Agent(
		task="""
		Navigate to https://x.com/i/flow/login
		Wait for the page to load.
		Use toggle_page_blur with blur=true to obscure sensitive information.
		Use fill_field action with field_name='username' (vault and item will use defaults).
		Click the Next button.
		Use fill_field action with field_name='password'.
		Click the Log in button.
		Once you've confirmed successful login, use toggle_page_blur with blur=false to reveal the page.
		""",
		browser_session=browser_session,
		llm=llm,
		tools=tools,
		file_system_path='./agent_data',
	)

	await agent.run()


async def advanced_example():
	"""Advanced usage: Explicit passing with multiple vaults."""
	# Create separate OnePassword instances for different vaults
	prod_op = OnePassword(default_vault='prod-secrets', default_item='X')
	dev_op = OnePassword(
		service_account_token='your_dev_token_here',  # Or reads from OP_SERVICE_ACCOUNT_TOKEN
		default_vault='dev-secrets',
		default_item='TestAccount',
	)

	# Pass OnePassword instance explicitly to Tools
	tools_prod = Tools(onepassword=prod_op)
	tools_dev = Tools(onepassword=dev_op)

	# Use different tools for different agents/tasks
	browser_session = Browser()
	llm = ChatOpenAI(model='o3')

	# Agent using prod credentials
	agent = Agent(
		task='Log into production X account',
		browser_session=browser_session,
		llm=llm,
		tools=tools_prod,
		file_system_path='./agent_data',
	)

	await agent.run()


if __name__ == '__main__':
	import asyncio

	# Run the simple example
	asyncio.run(simple_example())

	# Uncomment to run advanced example:
	# asyncio.run(advanced_example())
