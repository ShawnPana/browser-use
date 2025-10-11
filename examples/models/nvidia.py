"""
NVIDIA NIM API example.

@dev You need to add NVIDIA_API_KEY to your environment variables.
Get your API key from: https://build.nvidia.com/
"""

import asyncio
import os

from dotenv import load_dotenv

from browser_use import Agent
from browser_use.llm import ChatNVIDIA

load_dotenv()

nvidia_api_key = os.getenv('NVIDIA_API_KEY')
if nvidia_api_key is None:
	print('Make sure you have NVIDIA_API_KEY set:')
	print('export NVIDIA_API_KEY=your_key')
	print('\nGet your API key from: https://build.nvidia.com/')
	exit(0)


async def main():
	# Method 1: Direct instantiation with full model name
	llm = ChatNVIDIA(
		model='nvidia/llama-3.3-nemotron-super-49b-v1.5',
		api_key=nvidia_api_key,
		temperature=0.6,
		top_p=0.95,
		max_tokens=65536,
	)

	# Method 2: Using lazy import aliases (uncomment to try)
	# from browser_use import llm
	# llm = llm.nvidia_llama_3_3_nemotron_super_49b_v1_5

	agent = Agent(
		task='Go to google.com and search for "browser automation with AI"',
		llm=llm,
		use_vision=False,
	)

	await agent.run(max_steps=10)


asyncio.run(main())
