import requests
from dotenv import load_dotenv
import json
import os 

load_dotenv()

api_key = os.getenv("OPEN_ROUTER_API_KEY")
model = "deepseek/deepseek-chat-v3-0324:free"
base_url = "https://openrouter.ai/api/v1"


response = requests.post(
    url=f"{base_url}/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}" # bearer ek keyword he jo batata he ke ap token bhej rahe ho
    },
    data= json.dumps({
        "model":model,
        "messages":[
            {
                "role":"user",
                "content":"what is python"
            }
        ]
    })
)

data = response.json()
print(data["choices"][0]["message"]["content"])






