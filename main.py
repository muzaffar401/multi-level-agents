from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig, Runner, function_tool
import os
from dotenv import load_dotenv, find_dotenv
import chainlit as cl
import requests
from deep_translator import GoogleTranslator

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, PlainTextContent


load_dotenv(find_dotenv())

# API Keys and Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

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

# Tool definitions
@function_tool("weather")
def get_weather(city: str):
    try:
        if not WEATHER_API_KEY:
            return "Weather service is not configured. Please check the WEATHER_API_KEY environment variable."
            
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        print(f"Making weather API request for {city}")  # Debug log
        
        response = requests.get(url)
        print(f"Weather API response status: {response.status_code}")  # Debug log
        
        if response.status_code == 200:
            data = response.json()
            weather = data['weather'][0]['description']
            temp = data['main']['temp']
            humidity = data['main']['humidity']
            wind_speed = data['wind']['speed']
            
            return f"""Weather in {city}:
• Temperature: {temp}°C
• Conditions: {weather}
• Humidity: {humidity}%
• Wind Speed: {wind_speed} m/s"""
        elif response.status_code == 401:
            return "Weather service authentication failed. Please check the API key."
        elif response.status_code == 404:
            return f"City '{city}' not found. Please check the spelling and try again."
        else:
            return f"Failed to get weather for {city}. Status code: {response.status_code}"
            
    except Exception as e:
        print(f"Weather API error: {str(e)}")  # Debug log
        return f"An error occurred while fetching weather data: {str(e)}"

@function_tool("send_email")
async def send_email(to_email: str, subject: str, message: str):
    try:
        # Debug logging for environment variables
        print("Checking environment variables...")
        print(f"SENDGRID_API_KEY exists: {bool(SENDGRID_API_KEY)}")
        print(f"EMAIL_ADDRESS exists: {bool(os.getenv('EMAIL_ADDRESS'))}")
        
        if not SENDGRID_API_KEY:
            return "SendGrid API key is not configured. Please set the SENDGRID_API_KEY environment variable."
        
        sender_email = os.getenv("EMAIL_ADDRESS")
        if not sender_email:
            return "Sender email address is not configured. Please set the EMAIL_ADDRESS environment variable."
            
        print(f"Using sender email: {sender_email}")
        print(f"Sending to: {to_email}")
        print(f"Subject: {subject}")
        
        # Create a Mail object
        mail = Mail(
            from_email=Email(sender_email),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=PlainTextContent(message)
        )
        
        # Create a SendGridAPIClient
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        
        print("Attempting to send email using SendGrid...")
        # Send the email
        response = sg.send(mail)
        
        print(f"SendGrid response status code: {response.status_code}")
        print(f"SendGrid response body: {response.body}")
        print(f"SendGrid response headers: {response.headers}")

        if response.status_code >= 200 and response.status_code < 300:
            return f"Email sent successfully to {to_email} via SendGrid."
        else:
            error_message = f"Failed to send email via SendGrid. Status code: {response.status_code}"
            if response.status_code == 403:
                error_message += "\nThis might be due to:\n1. Invalid API key\n2. Unverified sender email\n3. Insufficient API key permissions"
            return error_message

    except Exception as e:
        error_msg = str(e)
        print(f"Detailed error: {error_msg}")
        if "403" in error_msg:
            return "SendGrid authentication failed. Please check:\n1. Your SendGrid API key is valid\n2. Your sender email is verified in SendGrid\n3. Your API key has the necessary permissions"
        return f"Failed to send email via SendGrid: {error_msg}"

@function_tool("news")
def get_news(query: str = None, category: str = None):
    base_url = "https://newsdata.io/api/1/latest"
    params = {
        "apikey": NEWS_API_KEY,
        "language": "en"
    }
    
    if query:
        params["q"] = query
    if category:
        params["category"] = category
    
    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        articles = data.get("results", [])
        
        if not articles:
            return "No news articles found for the given criteria."
        
        news_summary = "Here are the latest news articles:\n\n"
        for i, article in enumerate(articles[:5], 1):
            news_summary += f"{i}. {article['title']}\n"
            news_summary += f"   Source: {article['source_id']}\n"
            news_summary += f"   Description: {article.get('description', 'No description available')}\n"
            news_summary += f"   Link: {article.get('link', 'No link available')}\n\n"
        
        return news_summary
    else:
        return f"Failed to fetch news. Status code: {response.status_code}"

@function_tool("translate_text")
async def translate_text(text: str, target_language: str = "ur"):
    try:
        # Use deep-translator which is more reliable
        translator = GoogleTranslator(source='auto', target=target_language)
        translation = translator.translate(text)
        
        # Format the response
        response = f"Original: {text}\n"
        response += f"Translation: {translation}"
        
        return response
    except Exception as e:
        print(f"Translation error: {str(e)}")  # Add debug logging
        return f"Translation failed: {str(e)}"

# Define specialized agents
weather_agent = Agent(
    name="Weather Agent",
    instructions="You are a weather agent. Use the weather tool to provide weather information for specific cities. For non-weather queries, suggest using the general assistant.",
    tools=[get_weather]
)

translator_agent = Agent(
    name="Translator Agent",
    instructions="""You are a professional multilingual translator.
    Your responsibilities:
    1. Detect the source language automatically.
    2. Translate text into the requested target language.
    3. Use natural language and maintain proper grammar.
    4. Include pronunciation for different scripts.
    For non-translation queries, suggest using the general assistant.""",
    tools=[translate_text]
)

email_agent = Agent(
    name="Email Agent",
    instructions="You're an email sending agent. Validate email format and ensure all required information (recipient, subject, message) is provided before sending. For non-email tasks, suggest using the general assistant.",
    tools=[send_email]
)

news_agent = Agent(
    name="News Agent",
    instructions="You're a news agent providing latest news. Handle general news, category-specific news, and topic-specific news requests. For non-news queries, suggest using the general assistant.",
    tools=[get_news]
)

# Main agent that handles all queries and delegates to specialized agents
main_agent = Agent(
    name="Main Assistant",
    instructions="""You are a helpful assistant that can answer general questions and coordinate with specialized agents.
    When users ask about specific tasks:
    - For weather queries (containing words like 'weather', 'temperature', 'forecast'), use the weather tool
    - For email tasks (containing words like 'email', 'send', 'mail'), use the email tool
    - For translation requests (containing words like 'translate', 'translation'), use the translate_text tool
    - For news queries (containing words like 'news', 'latest', 'headlines'), use the news tool
    For general knowledge questions, provide direct answers.
    Always be helpful and informative.""",
    tools=[get_weather, send_email, get_news, translate_text]
)

@cl.on_chat_start
async def chat_start():
    cl.user_session.set("history", [])
    welcome_msg = """Welcome! I'm your multi-agent assistant. You can:
    1. Ask general questions (just ask normally)
    2. Check weather (ask about weather in any city)
    3. Translate text (ask to translate any text)
    4. Send emails (ask to send an email)
    5. Get news (ask about latest news or specific topics)
    How can I help you today? 😊"""
    await cl.Message(content=welcome_msg).send()

@cl.on_message
async def handle_message(message: cl.Message):
    try:
        history = cl.user_session.get("history")
        
        # Format messages for history
        history.append({"role": "user", "content": message.content})
        formatted_messages = [{"role": msg["role"].lower(), "content": msg["content"]} for msg in history]
        
        # Determine which agent should handle the query
        user_input = message.content.lower()
        agent_type = "General Assistant"
        
        if any(word in user_input for word in ["weather", "temperature", "forecast"]):
            agent_type = "Weather Agent"
        elif any(word in user_input for word in ["email", "send", "mail"]):
            agent_type = "Email Agent"
        elif any(word in user_input for word in ["translate", "translation"]):
            agent_type = "Translator Agent"
        elif any(word in user_input for word in ["news", "latest", "headlines"]):
            agent_type = "News Agent"
        
        # Show which agent is analyzing
        await cl.Message(
            content=f"🤖 {agent_type} is analyzing your query...",
            author=agent_type
        ).send()
        
        # Get response from main agent
        result = await Runner.run(
            starting_agent=main_agent,
            input=formatted_messages,
            run_config=config
        )
        
        # Update history and send response
        history.append({"role": "assistant", "content": result.final_output})
        cl.user_session.set("history", history)
        
        # Send the response with the agent's name
        await cl.Message(
            content=result.final_output,
            author=agent_type
        ).send()
        
    except Exception as e:
        print(f"An error occurred: {e}")
        await cl.Message(
            content=f"Sorry, an error occurred: {e}",
            author="System"
        ).send()

if __name__ == "__main__":
    cl.run()