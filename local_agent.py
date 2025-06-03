# ─── Imports ────────────────────────────────────────────────────────────────
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig, Runner, function_tool
import chainlit as cl
import os
from dotenv import load_dotenv, find_dotenv

# ─── Load Environment Variables ─────────────────────────────────────────────
load_dotenv(find_dotenv())
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ─── Math Tools ─────────────────────────────────────────────────────────────

@function_tool("add")
def add(a: float, b: float):
    print("adding")
    return f"The sum of {a} and {b} is {a + b}"

@function_tool("subtract")
def subtract(a: float, b: float):
    return f"The difference between {a} and {b} is {a - b}"

@function_tool("multiply")
def multiply(a: float, b: float):
    return f"The product of {a} and {b} is {a * b}"

@function_tool("divide")
def divide(a: float, b: float):
    if b == 0:
        return "Cannot divide by zero!"
    return f"The result of dividing {a} by {b} is {a / b}"

# ─── Model Setup ────────────────────────────────────────────────────────────

provider = AsyncOpenAI(api_key=GEMINI_API_KEY,base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=provider
)

config = RunConfig(
    model=model,
    model_provider=provider,
    tracing_disabled=True
)

# ─── Math Agent ─────────────────────────────────────────────────────────────

math_agent = Agent(
    name="Math Agent",
    instructions="Use the correct tool (add, subtract, multiply, divide) to answer math questions.",
    tools=[add, subtract, multiply, divide]
)

# ─── Chainlit Events ────────────────────────────────────────────────────────

@cl.on_chat_start
async def start():
    await cl.Message(
        content="👋 Hello! I'm your Math Assistant.\nYou can ask me to:\n- Add\n- Subtract\n- Multiply\n- Divide\n\nExample: `What is 10 plus 4?`"
    ).send()

@cl.on_message
async def handle_msg(message: cl.Message):
    result = await Runner.run(
        starting_agent=math_agent,
        input=message.content,
        run_config=config
    )

    await cl.Message(
        content=result.final_output,
        author="Math Agent"
    ).send()

# ─── Run App ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cl.run()
