import os
import requests
import uuid
import openai
from flask import Flask, request, jsonify, render_template

# Initialize the Flask application
app = Flask(__name__, template_folder='templates')

# Get the necessary variables from the environment
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configure the OpenAI library with the API key
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# This is the main route that will serve your index.html file
@app.route('/')
def index():
    """Renders the main chat interface."""
    return render_template('index.html')

# This endpoint handles the main chat functionality by calling the n8n webhook
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Receives chat messages from the frontend, extracts the latest user message,
    and forwards it to the n8n webhook in a simplified format.
    """
    if not N8N_WEBHOOK_URL:
        return jsonify({"error": "N8N_WEBHOOK_URL environment variable not set."}), 500

    data = request.json
    messages = data.get('messages')
    session_id = data.get('sessionId', str(uuid.uuid4())) # Use existing or create new session ID

    if not messages:
        return jsonify({"error": "No messages provided."}), 400

    # Extract the last message content to be used as 'chatInput'
    last_message = messages[-1].get('content', '')

    # The simplified payload that will be sent to your n8n workflow.
    n8n_payload = {
        "chatInput": last_message,
        "sessionId": session_id,
    }

    try:
        # Forward the request to your n8n webhook
        response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload)
        response.raise_for_status()  # Raise an exception for bad status codes

        # n8n is expected to return a JSON object
        n8n_response_data = response.json()
        
        # Handle cases where n8n might wrap the response in a 'json' key
        data_to_process = n8n_response_data.get('json', n8n_response_data)

        # Standardize the response for the frontend.
        final_data = {
            "reply": data_to_process.get('reply') or data_to_process.get('output'),
            "suggestions": data_to_process.get('suggestions', [])
        }

        if not final_data["reply"]:
            final_data["reply"] = "Sorry, I didn't get a valid response from the workflow."

        return jsonify(final_data)

    except requests.exceptions.RequestException as e:
        print(f"Error calling n8n webhook: {e}")
        return jsonify({"error": "Failed to communicate with the n8n webhook."}), 502
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# This endpoint now calls OpenAI directly for summarization
@app.route('/api/summarize', methods=['POST'])
def summarize():
    """
    Summarizes a chat session by calling the OpenAI API directly.
    """
    if not OPENAI_API_KEY:
        return jsonify({"summary": "OpenAI API key not configured."}), 500
    
    data = request.json
    messages = data.get('messages', [])
    if not messages:
        return jsonify({"summary": "No messages to summarize."}), 400
        
    # Construct the prompt for the summarization
    prompt_messages = messages + [{"role": "system", "content": "Summarize the following chat session in 5 words or less for a sidebar label."}]
    
    try:
        # Call OpenAI API directly for the summary
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=prompt_messages,
            max_tokens=20
        )
        summary = response.choices[0].message.content.strip().replace('"', '')
        return jsonify({"summary": summary})
        
    except Exception as e:
        print(f"Error calling OpenAI for summary: {e}")
        return jsonify({"summary": "Could not summarize."}), 500


if __name__ == '__main__':
    # This is for local development. In production, Gunicorn will be used.
    app.run(host='0.0.0.0', port=5000, debug=True)
