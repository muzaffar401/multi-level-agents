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

# Import libraries for location services
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# Import additional libraries for documentation analysis
import requests
import json
import time



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
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")  # API key for recipe service
OPENROUTE_API_KEY = os.getenv("OPENROUTE_API_KEY")  # API key for OpenRouteService

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

# 6. Health Information Tool: Provides health-related information from the local database
@function_tool("health_info")
def get_health_info(query: str, info_type: str = "medication"):
    """
    Provides health-related information from the local database.

    Args:
        query: The health-related query (e.g., condition name, symptom, medication).
        info_type: Type of information to fetch ('condition', 'symptom', or 'medication').

    Returns:
        A formatted string containing health information or a message if no information is found.
    """
    # Common medications database for quick reference
    common_medications = {
        "abdominal pain": {
            "name": "Common Medications for Abdominal Pain",
            "description": "Various medications can help with abdominal pain, depending on the cause.",
            "medications": [
                {
                    "name": "Antacids",
                    "description": "For acid-related pain and heartburn",
                    "examples": ["Tums", "Rolaids", "Maalox"]
                },
                {
                    "name": "Anti-spasmodics",
                    "description": "For cramping and spasms",
                    "examples": ["Hyoscyamine", "Dicyclomine"]
                },
                {
                    "name": "Pain relievers",
                    "description": "For general pain relief",
                    "examples": ["Acetaminophen (Tylenol)", "Ibuprofen (Advil)"]
                },
                {
                    "name": "Anti-gas medications",
                    "description": "For gas-related pain",
                    "examples": ["Simethicone (Gas-X)"]
                }
            ],
            "precautions": [
                "Always consult a doctor before taking any medication",
                "Some medications may interact with other drugs",
                "Follow dosage instructions carefully",
                "Seek immediate medical attention if pain is severe or persistent"
            ]
        },
        "headache": {
            "name": "Common Medications for Headache",
            "description": "Various medications can help with headache pain, depending on the type and severity.",
            "medications": [
                {
                    "name": "Pain relievers",
                    "description": "For general headache pain",
                    "examples": ["Acetaminophen (Tylenol)", "Ibuprofen (Advil)", "Aspirin"]
                },
                {
                    "name": "Migraine medications",
                    "description": "For migraine headaches",
                    "examples": ["Sumatriptan", "Rizatriptan"]
                }
            ],
            "precautions": [
                "Always consult a doctor before taking any medication",
                "Some medications may interact with other drugs",
                "Follow dosage instructions carefully",
                "Seek immediate medical attention if headache is severe or persistent"
            ]
        },
        "migraine": {
            "name": "Common Medications for Migraine",
            "description": "Migraine treatments can include both preventive and acute medications.",
            "medications": [
                {
                    "name": "Acute treatments",
                    "description": "Medications taken when a migraine attack begins",
                    "examples": ["Sumatriptan (Imitrex)", "Rizatriptan (Maxalt)", "Eletriptan (Relpax)"]
                },
                {
                    "name": "Pain relievers",
                    "description": "For mild to moderate migraine pain",
                    "examples": ["Acetaminophen (Tylenol)", "Ibuprofen (Advil)", "Naproxen (Aleve)"]
                },
                {
                    "name": "Anti-nausea medications",
                    "description": "For migraine-related nausea",
                    "examples": ["Metoclopramide", "Prochlorperazine"]
                }
            ],
            "precautions": [
                "Always consult a doctor before taking any medication",
                "Some medications may interact with other drugs",
                "Follow dosage instructions carefully",
                "Seek immediate medical attention if symptoms are severe",
                "Keep a migraine diary to track triggers and effectiveness of treatments"
            ]
        },
        "liver": {
            "name": "Common Medications for Liver Conditions",
            "description": "Liver conditions require careful management and specific medications based on the underlying cause.",
            "medications": [
                {
                    "name": "Hepatitis treatments",
                    "description": "For viral hepatitis",
                    "examples": ["Entecavir", "Tenofovir", "Sofosbuvir"]
                },
                {
                    "name": "Liver protectants",
                    "description": "To support liver function",
                    "examples": ["Ursodeoxycholic acid", "Silymarin (Milk thistle)"]
                },
                {
                    "name": "Pain management",
                    "description": "For liver-related pain",
                    "examples": ["Acetaminophen (in limited doses)", "Tramadol"]
                }
            ],
            "precautions": [
                "Always consult a doctor before taking any medication",
                "Avoid alcohol and certain medications that can harm the liver",
                "Regular liver function tests may be required",
                "Seek immediate medical attention for severe pain or jaundice",
                "Some medications may need dose adjustments based on liver function"
            ]
        },
        "diabetes": {
            "name": "Common Medications for Diabetes",
            "description": "Diabetes management involves various medications to control blood sugar levels.",
            "medications": [
                {
                    "name": "Insulin",
                    "description": "For type 1 diabetes and some type 2 cases",
                    "examples": ["Regular insulin", "NPH insulin", "Insulin glargine"]
                },
                {
                    "name": "Oral medications",
                    "description": "For type 2 diabetes",
                    "examples": ["Metformin", "Sulfonylureas", "DPP-4 inhibitors"]
                },
                {
                    "name": "GLP-1 receptor agonists",
                    "description": "Injectable medications for type 2 diabetes",
                    "examples": ["Liraglutide", "Dulaglutide", "Semaglutide"]
                }
            ],
            "precautions": [
                "Regular blood sugar monitoring is essential",
                "Follow a consistent meal schedule",
                "Be aware of signs of low blood sugar",
                "Keep emergency glucose tablets handy",
                "Regular check-ups with healthcare provider"
            ]
        },
        "hypertension": {
            "name": "Common Medications for High Blood Pressure",
            "description": "Various medications are used to control high blood pressure.",
            "medications": [
                {
                    "name": "ACE inhibitors",
                    "description": "Help relax blood vessels",
                    "examples": ["Lisinopril", "Enalapril", "Ramipril"]
                },
                {
                    "name": "Calcium channel blockers",
                    "description": "Help relax blood vessel muscles",
                    "examples": ["Amlodipine", "Diltiazem", "Verapamil"]
                },
                {
                    "name": "Diuretics",
                    "description": "Help remove excess water and salt",
                    "examples": ["Hydrochlorothiazide", "Furosemide", "Spironolactone"]
                }
            ],
            "precautions": [
                "Regular blood pressure monitoring",
                "Take medications at the same time daily",
                "Limit salt intake",
                "Regular exercise as recommended",
                "Avoid alcohol and smoking"
            ]
        },
        "asthma": {
            "name": "Common Medications for Asthma",
            "description": "Asthma treatment includes both rescue and controller medications.",
            "medications": [
                {
                    "name": "Quick-relief medications",
                    "description": "For immediate symptom relief",
                    "examples": ["Albuterol", "Levalbuterol", "Terbutaline"]
                },
                {
                    "name": "Controller medications",
                    "description": "For long-term control",
                    "examples": ["Inhaled corticosteroids", "Long-acting beta agonists", "Leukotriene modifiers"]
                },
                {
                    "name": "Combination inhalers",
                    "description": "Combine controller and rescue medications",
                    "examples": ["Advair", "Symbicort", "Dulera"]
                }
            ],
            "precautions": [
                "Keep rescue inhaler readily available",
                "Follow asthma action plan",
                "Regular check-ups with healthcare provider",
                "Monitor peak flow readings",
                "Avoid known triggers"
            ]
        },
        "depression": {
            "name": "Common Medications for Depression",
            "description": "Various medications are used to treat depression and related conditions.",
            "medications": [
                {
                    "name": "SSRIs",
                    "description": "Selective serotonin reuptake inhibitors",
                    "examples": ["Fluoxetine", "Sertraline", "Escitalopram"]
                },
                {
                    "name": "SNRIs",
                    "description": "Serotonin-norepinephrine reuptake inhibitors",
                    "examples": ["Venlafaxine", "Duloxetine", "Desvenlafaxine"]
                },
                {
                    "name": "Atypical antidepressants",
                    "description": "Other types of antidepressants",
                    "examples": ["Bupropion", "Mirtazapine", "Trazodone"]
                }
            ],
            "precautions": [
                "Take medications as prescribed",
                "Regular follow-up with healthcare provider",
                "Be aware of potential side effects",
                "Don't stop medication without consulting doctor",
                "Combine with therapy for best results"
            ]
        }
    }

    # Check if the query matches any common medication patterns
    query_lower = query.lower()
    
    # Extract the condition/symptom from the query
    for key in common_medications:
        if key in query_lower:
            med_info = common_medications[key]
            response_text = f"""Information about {med_info['name']}:
• Description: {med_info['description']}

Common Medications:"""
            
            for med in med_info['medications']:
                response_text += f"\n\n{med['name']}:"
                response_text += f"\n• Purpose: {med['description']}"
                response_text += f"\n• Examples: {', '.join(med['examples'])}"
            
            response_text += "\n\nImportant Precautions:"
            for precaution in med_info['precautions']:
                response_text += f"\n• {precaution}"
            
            response_text += "\n\nNote: This information is for educational purposes only. Please consult a healthcare professional for proper diagnosis and treatment."
            return response_text

    # If no match is found in the database
    return f"I don't have specific information about '{query}'. Please consult a healthcare professional for medical advice. You can ask about: {', '.join(common_medications.keys())}"

# 7. Recipe Tool: Fetches recipe information using the Spoonacular API
@function_tool("get_recipe")
def get_recipe(query: str, diet: str = None, cuisine: str = None):
    """
    Fetches recipe information using the Spoonacular API.

    Args:
        query: The recipe name or ingredients to search for.
        diet: Optional dietary restrictions (e.g., 'vegetarian', 'vegan', 'gluten-free').
        cuisine: Optional cuisine type (e.g., 'italian', 'mexican', 'indian').

    Returns:
        A formatted string containing recipe information.
    """
    if not SPOONACULAR_API_KEY:
        return "Recipe service is not configured. Please check the SPOONACULAR_API_KEY environment variable."

    # Construct the API URL
    base_url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "query": query,
        "addRecipeInformation": True,
        "number": 1,  # Get one recipe at a time
        "instructionsRequired": True,
        "fillIngredients": True
    }

    if diet:
        params["diet"] = diet
    if cuisine:
        params["cuisine"] = cuisine

    try:
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if not data.get("results"):
                return f"No recipes found for '{query}'."
            
            recipe = data["results"][0]
            
            # Format the recipe information
            recipe_info = f"""Recipe: {recipe['title']}

Preparation Time: {recipe.get('readyInMinutes', 'N/A')} minutes
Servings: {recipe.get('servings', 'N/A')}

Ingredients:
{chr(10).join(f'• {ingredient["original"]}' for ingredient in recipe.get('extendedIngredients', []))}

Instructions:
{recipe.get('instructions', 'No instructions available.')}

Nutrition Information:
• Calories: {recipe.get('nutrition', {}).get('nutrients', [{}])[0].get('amount', 'N/A')} kcal
• Protein: {next((n['amount'] for n in recipe.get('nutrition', {}).get('nutrients', []) if n['name'] == 'Protein'), 'N/A')}g
• Carbohydrates: {next((n['amount'] for n in recipe.get('nutrition', {}).get('nutrients', []) if n['name'] == 'Carbohydrates'), 'N/A')}g
• Fat: {next((n['amount'] for n in recipe.get('nutrition', {}).get('nutrients', []) if n['name'] == 'Fat'), 'N/A')}g

Source: {recipe.get('sourceUrl', 'N/A')}"""
            
            return recipe_info
        elif response.status_code == 401:
            return "Invalid API key for recipe service."
        else:
            return f"Failed to fetch recipe. Status: {response.status_code}"
    except Exception as e:
        return f"Error fetching recipe: {str(e)}"

# Add the motivation tool function
@function_tool("get_motivation")
def get_motivation(category: str = None):
    """
    Fetches motivational quotes using the ZenQuotes API.

    Args:
        category: Optional category of quotes (e.g., 'success', 'leadership', 'happiness').

    Returns:
        A formatted string containing motivational quotes.
    """
    try:
        # Base URL for the ZenQuotes API
        base_url = "https://zenquotes.io/api/quotes"
        
        # Parameters for the API request
        params = {
            "count": 3  # Get 3 quotes at a time
        }
        
        if category:
            params["category"] = category

        # Make the API request
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            quotes = response.json()
            
            # Format the quotes
            if isinstance(quotes, list):
                formatted_quotes = []
                for quote in quotes:
                    formatted_quote = f"""Quote: "{quote.get('q', '')}"
Author: {quote.get('a', 'Unknown')}
Category: {quote.get('c', 'General')}"""
                    formatted_quotes.append(formatted_quote)
                
                return "\n\n---\n\n".join(formatted_quotes)
            else:
                return "No quotes found."
        else:
            return f"Failed to fetch quotes. Status: {response.status_code}"
    except Exception as e:
        return f"Error fetching quotes: {str(e)}"

# Add the location tool function
@function_tool("get_location_info")
def get_location_info(pickup_location: str, dropoff_location: str):
    """
    Gets location information and calculates route between two locations using OpenStreetMap services.

    Args:
        pickup_location: The starting location (address or place name).
        dropoff_location: The destination location (address or place name).

    Returns:
        A formatted string containing location details and route information.
    """
    try:
        # Initialize the Nominatim geocoder with a proper user agent
        geolocator = Nominatim(
            user_agent="MyLocationApp/1.0 (https://github.com/yourusername/yourrepo; your@email.com)",
            timeout=10
        )

        # Check if locations are too general (just countries)
        def is_country_only(location):
            common_countries = [
                "usa", "united states", "america", "canada", "mexico", "uk", "united kingdom",
                "england", "france", "germany", "china", "india", "australia", "pakistan"
            ]
            location_lower = location.lower()
            return any(country in location_lower for country in common_countries)

        if is_country_only(pickup_location) or is_country_only(dropoff_location):
            return """I need more specific locations to calculate the distance. Please provide cities or specific addresses.

For example, instead of:
- "USA to Canada"
Try:
- "New York to Toronto"
- "Los Angeles to Vancouver"
- "Chicago to Montreal"

This will help me provide accurate distance and route information."""

        # Function to geocode a location using Nominatim
        def geocode_location(location):
            try:
                # Add a small delay to respect rate limits
                time.sleep(1)
                result = geolocator.geocode(location)
                if result:
                    return {
                        "address": result.address,
                        "latitude": result.latitude,
                        "longitude": result.longitude,
                        "raw": result.raw
                    }
                return None
            except Exception as e:
                print(f"Geocoding error for {location}: {str(e)}")
                return None

        # Get coordinates for pickup location
        print(f"Processing pickup location: {pickup_location}")
        pickup_info = geocode_location(pickup_location)
        if not pickup_info:
            return f"Could not find coordinates for pickup location: {pickup_location}. Please try with a more specific address."

        # Get coordinates for dropoff location
        print(f"Processing dropoff location: {dropoff_location}")
        dropoff_info = geocode_location(dropoff_location)
        if not dropoff_info:
            return f"Could not find coordinates for dropoff location: {dropoff_location}. Please try with a more specific address."

        # Calculate straight-line distance using geodesic
        straight_distance = geodesic(
            (pickup_info["latitude"], pickup_info["longitude"]),
            (dropoff_info["latitude"], dropoff_info["longitude"])
        ).kilometers

        # Get driving route using OSRM
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{pickup_info['longitude']},{pickup_info['latitude']};{dropoff_info['longitude']},{dropoff_info['latitude']}?overview=full"
        
        response = requests.get(osrm_url)
        if response.status_code == 200:
            route_data = response.json()
            if route_data["code"] == "Ok":
                route = route_data["routes"][0]
                driving_distance = route["distance"] / 1000  # Convert to kilometers
                duration = route["duration"] / 60  # Convert to minutes

                # Format the response
                response = f"""Location Information:

Pickup Location:
• Address: {pickup_info['address']}
• Coordinates: {pickup_info['latitude']:.6f}, {pickup_info['longitude']:.6f}

Dropoff Location:
• Address: {dropoff_info['address']}
• Coordinates: {dropoff_info['latitude']:.6f}, {dropoff_info['longitude']:.6f}

Route Information:
• Driving Distance: {driving_distance:.2f} km
• Straight-line Distance: {straight_distance:.2f} km
• Estimated Duration: {duration:.0f} minutes
• Average Speed: {(driving_distance / (duration/60)):.1f} km/h

Note: This information is provided by OpenStreetMap and is free to use under the Open Database License."""

                return response
            else:
                return "Could not calculate the driving route. The locations might be too far apart or not connected by roads."
        else:
            return f"Error getting route information. Status code: {response.status_code}"

    except Exception as e:
        print(f"General error: {str(e)}")
        return f"Error getting location information: {str(e)}"

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

# Health Agent: Handles health-related queries by using the health_info tool
health_agent = Agent(
    name="Health Agent",
    instructions="""Use the health_info tool to provide health-related information.
For conditions, symptoms, or medications, specify the appropriate info_type.
Always include a disclaimer about consulting healthcare professionals.
When asked about medications, first check the common medications database.""",
    tools=[get_health_info]
)

# Recipe Agent: Handles recipe-related queries by using the get_recipe tool
recipe_agent = Agent(
    name="Recipe Agent",
    instructions="""Use the get_recipe tool to provide recipe information.
When given a recipe request:
1. Extract the recipe name or ingredients from the query
2. Look for any dietary restrictions or cuisine preferences
3. Provide detailed recipe information including ingredients and instructions
4. Include nutritional information when available""",
    tools=[get_recipe]
)

# Motivation Agent: Handles motivational quotes by using the get_motivation tool
motivation_agent = Agent(
    name="Motivation Agent",
    instructions="""Use the get_motivation tool to provide inspirational quotes.
When given a motivation request:
1. Extract any specific category or theme from the query
2. Provide multiple motivational quotes
3. Include the author and category for each quote
4. Format the quotes in an inspiring way""",
    tools=[get_motivation]
)

# Location Agent: Handles location-related queries by using the get_location_info tool
location_agent = Agent(
    name="Location Agent",
    instructions="""Use the get_location_info tool to provide location and distance information.
When given a location request:
1. Extract pickup and dropoff locations from the query
2. Provide detailed location information including addresses and coordinates
3. Calculate and display the distance between locations
4. Format the information in a clear and organized way""",
    tools=[get_location_info]
)

# Main Assistant Agent - This is the primary agent that receives user input
# It's responsible for understanding the user's intent and delegating the task
# to the appropriate specialized agent/tool based on its instructions.
main_agent = Agent(
    name="Main Assistant",
    instructions="""
I am a helpful assistant that coordinates specialized agents for specific tasks:
- For weather: use the weather tool
- For email: use the email tool
- For translation: use the translate_text tool
- For news: use the news tool
- For cryptocurrency prices: use the crypto_price tool
- For health information: use the health_info tool
- For recipes: use the get_recipe tool
- For motivation: use the get_motivation tool
- For location and distance: use the get_location_info tool
For other general questions, answer directly.
""",
    tools=[get_weather, send_email, get_news, translate_text, get_crypto_price, get_health_info, get_recipe, get_motivation, get_location_info]
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
6. Getting health information
7. Finding recipes
8. Getting motivational quotes
9. Finding locations and routes
10. Or any general question
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
    # Get the conversation history for this session
    history = cl.user_session.get("history")
    history.append({"role": "user", "content": message.content})

    # Analyze user input
    user_input = message.content.lower()
    agent_type = "General Assistant"

    # Use keywords to determine the appropriate agent
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
    elif any(word in user_input for word in ["health", "medical", "condition", "symptom", "medication", "disease", "illness", "medicine", "med", "pain", "ache", "migraine", "headache"]):
        agent_type = "Health Agent"
    elif any(word in user_input for word in ["recipe", "cook", "food", "dish", "meal", "ingredients", "how to make"]):
        agent_type = "Recipe Agent"
    elif any(word in user_input for word in ["motivation", "inspire", "quote", "inspirational", "motivational", "encourage", "uplift"]):
        agent_type = "Motivation Agent"
    elif any(word in user_input for word in ["location", "distance", "pickup", "dropoff", "pick up", "drop off", "from", "to", "between", "route", "directions"]):
        agent_type = "Location Agent"

    # Send processing message
    await cl.Message(
        content=f"🤖 {agent_type} is analyzing your query...",
        author=agent_type
    ).send()

    # Run the main agent
    result = await Runner.run(
        starting_agent=main_agent,
        input=[{"role": "user", "content": message.content}],
        run_config=config
    )

    # Update history and send response
    history.append({"role": "assistant", "content": result.final_output})
    cl.user_session.set("history", history)

    await cl.Message(
        content=result.final_output,
        author=agent_type
    ).send()

# --- Run the Chainlit App ---

# This standard Python construct ensures that the Chainlit app runs only when the script is executed directly
if __name__ == "__main__":
    cl.run() # Start the Chainlit application
