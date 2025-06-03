from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig, Runner, function_tool
import os
from dotenv import load_dotenv, find_dotenv
import chainlit as cl
import requests

load_dotenv(find_dotenv())

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Check for API keys
if not GEMINI_API_KEY or not WEATHER_API_KEY:
    print("Error: Required API keys not found in environment variables.")

# Provider and Model setup
provider = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=provider
)

config = RunConfig(
    model=model,
    model_provider=provider,
    tracing_disabled=True
)

# Weather tool
@function_tool("weather")
def get_weather(city: str):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        weather = data['weather'][0]['description']
        temp = data['main']['temp']
        return f"Weather in {city}: {weather}, Temperature: {temp}°C"
    else:
        return f"Failed to get weather for {city}. Status code: {response.status_code}"

# Define agents
general_agent = Agent(
    name="General Assistant",
    instructions="You are a helpful assistant that can answer general questions on any topic. If a user asks about weather or translation, kindly inform them to use the specific weather or translator commands.",
)

weather_agent = Agent(
    name="Weather Agent",
    instructions="You are a weather agent. If user asks for weather of any specific city, use the weather tool to give the answer. For non-weather queries, suggest using the general assistant.",
    tools=[get_weather]
)

translator_agent = Agent(
    name="Translator Agent",
    instructions="""You are a professional multilingual translator.
    Your responsibilities:
    1. Detect the source language of the user's input automatically.
    2. Translate the text into the requested target language.
    3. Use simple, natural language and maintain proper grammar.
    4. If the target language uses a different script, include both the translation and pronunciation.
    For non-translation queries, suggest using the general assistant."""
)

@cl.on_chat_start
async def chat_start():
    cl.user_session.set("history", [])
    welcome_msg = """Welcome! I'm your multi-agent assistant. You can:
    1. Ask general questions (just ask normally)
    2. Check weather (start with 'weather in [city]')
    3. Translate text (start with 'translate [text] to [language]')
    How can I help you today? 😊"""
    await cl.Message(content=welcome_msg).send()

@cl.on_message
async def handle_message(message: cl.Message):
    try:
        history = cl.user_session.get("history")
        user_input = message.content.lower()
        
        # Select appropriate agent based on input
        if user_input.startswith("weather in"):
            current_agent = weather_agent
        elif user_input.startswith("translate"):
            current_agent = translator_agent
        else:
            current_agent = general_agent
            
        # Format messages for history
        history.append({"role": "user", "content": message.content})
        formatted_messages = [{"role": msg["role"].lower(), "content": msg["content"]} for msg in history]
        
        # Get response from selected agent
        result = await Runner.run(
            starting_agent=current_agent,
            input=formatted_messages,
            run_config=config
        )
        
        # Update history and send response
        history.append({"role": "assistant", "content": result.final_output})
        cl.user_session.set("history", history)
        await cl.Message(content=result.final_output).send()
        
    except Exception as e:
        print(f"An error occurred: {e}")
        await cl.Message(content=f"Sorry, an error occurred: {e}").send()