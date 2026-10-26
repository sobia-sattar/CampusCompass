import azure.functions as func
import logging
import json
import os
import requests

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Environment Variables
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("PROJECT_API_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("PROJECT_ENDPOINT")
DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-mini")

@app.route(route="CampusCompassAPI")
def CampusCompassAPI(req: func.HttpRequest) -> func.HttpResponse:
    # 1. Meta Webhook Handshake (GET)
    if req.method == 'GET':
        mode = req.params.get('hub.mode')
        token = req.params.get('hub.verify_token')
        challenge = req.params.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return func.HttpResponse(challenge, status_code=200)
        return func.HttpResponse("Verification failed", status_code=403)

    # 2. Incoming WhatsApp Message (POST)
    elif req.method == 'POST':
        try:
            body = req.get_json()
            
            entry = body.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])

            if messages:
                message = messages[0]
                from_number = message.get('from')
                
                if message.get('type') == 'text':
                    user_text = message.get('text', {}).get('body', '')
                    
                    # AI Answer
                    ai_reply = get_openai_response(user_text)
                    
                    # Send Back to WhatsApp
                    send_whatsapp(from_number, ai_reply)

            return func.HttpResponse("OK", status_code=200)

        except Exception as e:
            logging.error(f"Execution Exception: {str(e)}")
            return func.HttpResponse("OK", status_code=200)

def get_openai_response(user_text):
    """Direct Azure OpenAI REST API Request"""
    try:
        # Endpoint formatting
        base_url = AZURE_OPENAI_ENDPOINT.rstrip('/')
        url = f"{base_url}/openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version=2024-02-15-preview"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are Campus Saathi - A helpful assistant for Software Department students of Mehran University Of Engineering And Technology Jamshoro."
                },
                {"role": "user", "content": user_text}
            ],
            "max_tokens": 500
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data['choices'][0]['message']['content']
        else:
            logging.error(f"OpenAI Call Error: {resp.text}")
            return "Apologies, I am unable to process your request at the moment."
            
    except Exception as ex:
        logging.error(f"OpenAI Exception: {str(ex)}")
        return "Internal system error occurred."

def send_whatsapp(to_phone, message_text):
    """Send Message back to WhatsApp User"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text}
    }
    requests.post(url, headers=headers, json=payload, timeout=10)
