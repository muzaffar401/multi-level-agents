from dotenv import load_dotenv
import os 
from agents import Agent, OpenAIChatCompletionsModel,AsyncOpenAI, Runner, set_tracing_disabled
import asyncio

load_dotenv()

api_key = os.getenv("OPEN_ROUTER_API_KEY")
model = "deepseek/deepseek-chat-v3-0324:free"
base_url = "https://openrouter.ai/api/v1"

client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url
)

model = OpenAIChatCompletionsModel(model=model, openai_client=client)


set_tracing_disabled(disabled=True)

async def main():
    # This agent will use the custom LLM provider
    agent = Agent(
        name="Assistant",
        instructions="You only respond in haikus.",
        model=model,
    )

    result = await Runner.run(
        agent,
        "Tell me about recursion in programming.",
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())










