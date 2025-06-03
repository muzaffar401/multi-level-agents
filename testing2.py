# --- Library Imports ---

# Import necessary components from the agents SDK for creating agents and running them
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig, Runner, function_tool

# Import OS for interacting with the operating system (like accessing environment variables)
import os
# Import libraries to load environment variables from a .env file
from dotenv import load_dotenv, find_dotenv

# Import Chainlit library for creating the interactive chat interface
import chainlit as cl

# Import libraries for making HTTP requests (used by weather and news tools)
import requests
# Import libraries for sending emails via SMTP
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# Import library for text translation
from deep_translator import GoogleTranslator

# --- Load Environment Variables ---

# Load environment variables from the .env file (this allows you to keep sensitive info outside the code)
# find_dotenv() automatically searches for the .env file in the directory hierarchy
load_dotenv(find_dotenv())

# --- API Keys and Configuration ---

# Get API keys and sensitive information from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # API key for accessing the Gemini model
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY") # API key for the weather service
NEWS_API_KEY = os.getenv("NEWS_API_KEY") # API key for the news service
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS") # Your email address used as the sender
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # Your email app password (required for app login, not your main password)
COINDESK_API_KEY = os.getenv("COINDESK_API_KEY") # API key for CoinDesk cryptocurrency data

# SMTP Configuration (for sending emails via a standard SMTP server like Gmail)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com") # Get SMTP server address from env, default to Gmail
SMTP_PORT = int(os.getenv("SMTP_PORT", "587")) # Get SMTP port from env, default to 587 (TLS)

# --- AI Model Setup (Gemini) ---

# Setup AsyncOpenAI client, configuring it to use the Gemini API endpoint
provider = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/" # Google's API endpoint for Gemini via OpenAI SDK
)

# Configuration for the specific Gemini model we will use (using a flash model for speed/cost efficiency)
model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash", # Specifying the model name
    openai_client=provider # Associating the model with our configured provider
)

# Define the run configuration for how the model should be executed
config = RunConfig(
    model=model, # Specify the model to use for runs
    model_provider=provider, # Specify the provider for the model
    tracing_disabled=True # Set to False to see detailed model tracing (tool calls, reasoning) in the Chainlit UI
)

# --- Tools Definition (Functions for each agent's task) ---

# Tools are functions that agents can call to perform specific actions.
# The @function_tool decorator registers the function as a callable tool for the agents.

# 1. Weather Tool: Fetches current weather data for a given city
@function_tool("weather")
def get_weather(city: str):
    """
    Fetches current weather data for a specified city using the OpenWeatherMap API.

    Args:
        city: The name of the city for which to get weather information.

    Returns:
        A formatted string containing weather details (temperature, conditions, humidity, wind speed)
        or an error message if the API request fails or the city is not found.
    """
    # Check if the OpenWeatherMap API key is available in environment variables
    if not WEATHER_API_KEY:
        return "Weather service is not configured. Please check the WEATHER_API_KEY environment variable."
        
    # Construct the API URL with the city and API key
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric" # units=metric for Celsius
    
    # Make the HTTP GET request to the weather API
    response = requests.get(url)
    
    # Process the API response based on status code
    if response.status_code == 200: # Success
        data = response.json()
        # Extract relevant weather information from the JSON response
        weather = data['weather'][0]['description']
        temp = data['main']['temp']
        humidity = data['main']['humidity']
        wind_speed = data['wind']['speed']
        
        # Return formatted weather information as a multi-line string
        return f"""Weather in {city}:
• Temperature: {temp}°C
• Conditions: {weather}
• Humidity: {humidity}%
• Wind Speed: {wind_speed} m/s"""
    elif response.status_code == 401: # Unauthorized - likely an invalid API key
        return "Invalid weather API key."
    elif response.status_code == 404: # Not Found - city not recognized by the API
        return f"City '{city}' not found."
    else:
        # Handle other potential API errors with their status code
        return f"Failed to get weather. Status: {response.status_code}"

# 2. Email Tool: Sends an email to a specified recipient using SMTP
@function_tool("send_email")
def send_email(to_email: str, subject: str, message: str):
    """
    Sends an email using SMTP. Requires EMAIL_ADDRESS and EMAIL_PASSWORD environment variables.

    Args:
        to_email: The recipient's email address.
        subject: The subject of the email.
        message: The plain text body of the email.

    Returns:
        A success message if the email is sent successfully, or an error message if sending fails.
    """
    # Check if email sender credentials are set in environment variables
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return "Email configuration is missing. Please set both EMAIL_ADDRESS and EMAIL_PASSWORD in your .env file."
        
    # Create the email message object using MIMEMultipart to handle different parts (like text)
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS # Set the sender address
    msg['To'] = to_email # Set the recipient address
    msg['Subject'] = subject # Set the email subject
    
    # Attach the plain text body to the email message
    msg.attach(MIMEText(message, 'plain'))
    
    # Create an SMTP session and send the email within a 'with' statement
    # This ensures the connection is properly closed afterwards.
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        
        server.starttls()  # Upgrade the connection to a secure encrypted one using TLS
        
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD) # Login to the SMTP server using credentials
        
        server.send_message(msg) # Send the constructed email message
        
    # Return a success message if no exception occurred
    return f"Email successfully sent to {to_email}!"

# 3. News Tool: Fetches the latest news or news about a specific topic
@function_tool("news")
def get_news(query: str = None, category: str = None):
    """
    Fetches the latest news articles based on a query or category using the NewsData.io API.

    Args:
        query: A search query for specific news topics (optional).
        category: A category to filter news articles (e.g., 'technology', 'sports') (optional).

    Returns:
        A formatted string containing a summary of recent news articles or a message
        indicating no articles were found or an error occurred.
    """
    # Base URL for the news API
    base_url = "https://newsdata.io/api/1/latest"
    
    # Parameters dictionary for the API request
    params = {
        "apikey": NEWS_API_KEY, # Include the API key
        "language": "en" # Requesting news in English language
    }
    
    # Add query and category to parameters if they were provided by the user
    if query:
        params["q"] = query
    if category:
        params["category"] = category
    
    # Make the HTTP GET request to the news API with the specified parameters
    response = requests.get(base_url, params=params)
    
    # Process the API response based on status code
    if response.status_code == 200: # Success
        data = response.json() # Parse the JSON response body
        articles = data.get("results", []) # Get the list of articles, default to an empty list if 'results' key is missing
        
        # Check if any articles were returned in the response
        if not articles:
            return "No news found." # Inform the user if no articles match the criteria
        
        # Build a summary string of the top articles
        news_summary = "Here are the latest news articles:\n\n"
        # Iterate through the first 5 articles (or fewer if less than 5) and format the summary for each
        for i, article in enumerate(articles[:5], 1): # enumerate adds a counter starting from 1
            news_summary += f"{i}. {article['title']}\n" # Add article title
            news_summary += f"   Source: {article['source_id']}\n" # Add article source
            news_summary += f"   Description: {article.get('description', 'No description')}\n" # Add description, with a default if missing
            news_summary += f"   Link: {article.get('link', 'No link')}\n\n" # Add link, with a default if missing
        
        return news_summary # Return the formatted summary
    else:
        # Handle API errors with their status code
        return f"News fetch failed. Status: {response.status_code}" # Inform the user about the failure and status code

# 4. Translate Tool: Translates text from one language to another
@function_tool("translate_text")
async def translate_text(text: str, target_language: str = "ur"):
    """
    Translates text to a target language using Google Translator via the deep-translator library.

    Args:
        text: The text to translate.
        target_language: The language code for the target language (defaults to "ur" - Urdu).

    Returns:
        A formatted string showing the original text and its translation, or an error message if translation fails.
    """
    # Use deep-translator which is often more reliable for various languages than simple requests
    translator = GoogleTranslator(source='auto', target=target_language) # Auto-detect source language
    translation = translator.translate(text) # Perform the translation
    
    # Format the response string to show both original and translated text
    response = f"Original: {text}\nTranslation: {translation}"
    
    return response # Return the formatted translation result

# 5. Cryptocurrency Tool: Fetches current cryptocurrency prices using CoinGecko API
@function_tool("crypto_price")
def get_crypto_price(crypto: str = "bitcoin"):
    """
    Fetches current cryptocurrency price data using the CoinGecko API.

    Args:
        crypto: The cryptocurrency name or symbol (e.g., "bitcoin", "solana", "btc", "sol").
                Defaults to "bitcoin".

    Returns:
        A formatted string containing the current price and other relevant information,
        or an error message if the API request fails.
    """
    # Map common symbols to their CoinGecko IDs
    crypto_map = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "sol": "solana",
        "bitcoin": "bitcoin",
        "ethereum": "ethereum",
        "solana": "solana"
    }
    
    # Convert input to lowercase and map to CoinGecko ID if it's a known symbol
    crypto = crypto.lower()
    crypto_id = crypto_map.get(crypto, crypto)
    
    # Construct the API URL with the cryptocurrency ID
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=usd,gbp,eur&include_24hr_change=true"
    
    try:
        # Make the HTTP GET request to the CoinGecko API
        response = requests.get(url)
        
        # Process the API response based on status code
        if response.status_code == 200:  # Success
            data = response.json()
            
            # Check if we got data for the requested cryptocurrency
            if crypto_id in data:
                price_data = data[crypto_id]
                price_usd = price_data.get('usd', 0)
                price_gbp = price_data.get('gbp', 0)
                price_eur = price_data.get('eur', 0)
                change_24h = price_data.get('usd_24h_change', 0)
                
                # Format the response with prices in different currencies
                return f"""Current {crypto_id.upper()} Prices:
• USD: ${price_usd:,.2f}
• GBP: £{price_gbp:,.2f}
• EUR: €{price_eur:,.2f}
24h Change: {change_24h:+.2f}%"""
            else:
                return f"Could not find price data for {crypto}. Please check the cryptocurrency name or symbol."
        elif response.status_code == 404:
            return f"Could not find cryptocurrency '{crypto}'. Please check the name or symbol and try again."
        else:
            return f"Failed to get cryptocurrency price. Status: {response.status_code}"
    except Exception as e:
        return f"Error retrieving cryptocurrency price: {str(e)}"

# --- Specialized Agents (An agent for each task) ---

# Agents are defined with a name, instructions (guiding the model's behavior), and a list of tools they can use.

# Weather Agent: Handles weather-related queries by using the get_weather tool.
weather_agent = Agent(
    name="Weather Agent",
    instructions="Use the weather tool for weather-related questions.",
    tools=[get_weather]
)

# Translator Agent: Handles translation requests by using the translate_text tool.
translator_agent = Agent(
    name="Translator Agent",
    instructions="Automatically detect the source language and translate the text.",
    tools=[translate_text]
)

# Email Agent: Responsible for sending emails by using the send_email tool.
email_agent = Agent(
    name="Email Agent",
    instructions="Handle tasks related to sending emails.",
    tools=[send_email]
)

# News Agent: Fetches and provides news updates by using the get_news tool.
news_agent = Agent(
    name="News Agent",
    instructions="Use the news tool to get news updates.",
    tools=[get_news]
)

# Crypto Agent: Handles cryptocurrency-related queries by using the crypto_price tool
crypto_agent = Agent(
    name="Crypto Agent",
    instructions="Use the crypto_price tool to get current cryptocurrency prices.",
    tools=[get_crypto_price]
)

# Main Assistant Agent - This is the primary agent that receives user input
# It's responsible for understanding the user's intent and delegating the task
# to the appropriate specialized agent/tool based on its instructions.
main_agent = Agent(
    name="Main Assistant",
    # Instructions for the main assistant, explaining its capabilities and how it delegates tasks.
    # These instructions are crucial for the model to understand when to use which tool.
    instructions="""
I am a helpful assistant that coordinates specialized agents for specific tasks:
- For weather: use the weather tool
- For email: use the email tool
- For translation: use the translate_text tool
- For news: use the news tool
- For cryptocurrency prices: use the crypto_price tool
For other general questions, answer directly.
""",
    tools=[get_weather, send_email, get_news, translate_text, get_crypto_price] # List all available tools that the main agent can potentially use or delegate to.
)

# --- Chainlit Handlers (Chat Start and User Messages) ---

# These functions are called by the Chainlit framework in response to user interactions.

# Handles the chat session start event when a new chat is initiated.
@cl.on_chat_start
async def chat_start():
    # Initialize user message history for the current session. This history is used to provide context to the agent.
    cl.user_session.set("history", [])
    # Define and send a welcome message to the user at the beginning of the chat.
    welcome_msg = """Welcome! I'm your AI Assistant. I can help you with:
1. Checking the weather
2. Translating text
3. Sending emails
4. Getting news
5. Checking cryptocurrency prices
6. Or any general question
How can I help you today? 😊"""
    await cl.Message(content=welcome_msg).send() # Send the welcome message to the chat interface

# Handles incoming messages from the user.
@cl.on_message
async def handle_message(message: cl.Message):
    """
    Processes incoming user messages, determines the appropriate agent, and runs the agent.

    Args:
        message: The incoming message from the user (a Chainlit Message object).
    """
    # Get the conversation history for this session to provide context to the agent.
    history = cl.user_session.get("history")
    # Add the current user message to the history list.
    history.append({"role": "user", "content": message.content})

    # Analyze user input (converted to lowercase for case-insensitive matching) to determine the appropriate agent or task.
    user_input = message.content.lower()
    agent_type = "General Assistant" # Default agent if no specific task keyword is detected

    # Use keywords within the user input to decide which specialized agent should handle the query.
    # This is a simple keyword-based routing mechanism.
    if any(word in user_input for word in ["weather", "temperature", "forecast"]):
        agent_type = "Weather Agent"
    elif any(word in user_input for word in ["email", "send", "mail"]):
        agent_type = "Email Agent"
    elif any(word in user_input for word in ["translate", "translation"]):
        agent_type = "Translator Agent"
    elif any(word in user_input for word in ["news", "latest", "headlines"]):
        agent_type = "News Agent"
    elif any(word in user_input for word in ["crypto", "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "price"]):
        agent_type = "Crypto Agent"

    # Send a message to the chat indicating which agent is processing the query.
    await cl.Message(
        content=f"🤖 {agent_type} is analyzing your query...", # Inform the user about the processing agent
        author=agent_type # Set the author of the message to the agent name
    ).send()

    # Run the main agent with the current message as input.
    # The main agent's instructions and available tools will allow it to decide whether to handle the query itself
    # or delegate to one of the specialized agents implicitly by calling the appropriate tool.
    result = await Runner.run(
        starting_agent=main_agent,
        input=[{"role": "user", "content": message.content}], # Pass the current message as a list of messages (context) to the agent
        run_config=config # Provide the model configuration for the runner
    )

    # Store the assistant's final response (the output from the runner) in the history.
    history.append({"role": "assistant", "content": result.final_output})
    # Update the session history stored in Chainlit.
    cl.user_session.set("history", history)

    # Send the final result back to the user in the chat interface.
    await cl.Message(
        content=result.final_output,
        author=agent_type # Set the author of the final message to the agent that handled it
    ).send()

# --- Run the Chainlit App ---

# This standard Python construct ensures that the Chainlit app runs only when the script is executed directly
if __name__ == "__main__":
    cl.run() # Start the Chainlit application
