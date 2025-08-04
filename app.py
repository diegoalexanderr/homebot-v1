import os
import requests
import uuid
from flask import Flask, request, jsonify, render_template

# Initialize the Flask application
app = Flask(__name__, template_folder='templates')

# Get the necessary variables from the environment
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') # This will be passed to n8n

# This is the main route that will serve your index.html file
@app.route('/')
def index():
    """Renders the main chat interface."""
    return render_template('index.html')

# This endpoint handles the main chat functionality by calling the n8n webhook
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Receives chat messages and a session ID from the frontend,
    and forwards them to the n8n webhook for processing.
    """
    if not N8N_WEBHOOK_URL or not OPENAI_API_KEY:
        return jsonify({"error": "N8N_WEBHOOK_URL or OPENAI_API_KEY environment variable not set."}), 500

    data = request.json
    messages = data.get('messages')
    session_id = data.get('sessionId', str(uuid.uuid4())) # Use existing or create new session ID

    if not messages:
        return jsonify({"error": "No messages provided."}), 400

    # The payload that will be sent to your n8n workflow
    n8n_payload = {
        "task": "chat",
        "sessionId": session_id,
        "messages": messages,
        "api_key": OPENAI_API_KEY
    }

    try:
        # Forward the request to your n8n webhook
        response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload)
        response.raise_for_status()  # Raise an exception for bad status codes

        # n8n is expected to return a JSON object with 'reply' and 'suggestions'
        n8n_response_data = response.json()
        
        # Handle cases where n8n might wrap the response
        final_data = n8n_response_data.get('json', n8n_response_data)

        return jsonify(final_data)

    except requests.exceptions.RequestException as e:
        print(f"Error calling n8n webhook: {e}")
        return jsonify({"error": "Failed to communicate with the n8n webhook."}), 502
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# This endpoint handles the summary generation by calling the n8n webhook
@app.route('/api/summarize', methods=['POST'])
def summarize():
    """
    Receives messages for summarization and forwards them to the n8n webhook
    with a 'summarize' task flag.
    """
    if not N8N_WEBHOOK_URL or not OPENAI_API_KEY:
        return jsonify({"error": "N8N_WEBHOOK_URL or OPENAI_API_KEY environment variable not set."}), 500
    
    data = request.json
    messages = data.get('messages')
    if not messages:
        return jsonify({"error": "No messages provided for summary."}), 400
        
    # The payload for the summarization task
    n8n_payload = {
        "task": "summarize",
        "messages": messages,
        "api_key": OPENAI_API_KEY
    }
    
    try:
        # Forward the request to your n8n webhook
        response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload)
        response.raise_for_status()
        
        n8n_response_data = response.json()
        final_data = n8n_response_data.get('json', n8n_response_data)

        return jsonify(final_data)
        
    except Exception as e:
        print(f"Error calling n8n for summary: {e}")
        return jsonify({"error": "Failed to generate summary via n8n"}), 500


if __name__ == '__main__':
    # This is for local development. In production, Gunicorn will be used.
    app.run(host='0.0.0.0', port=5000, debug=True)
