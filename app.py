import os
import requests
import uuid
import openai
import json
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

    last_message = messages[-1].get('content', '')
    n8n_payload = { "chatInput": last_message, "sessionId": session_id }

    try:
        response = requests.post(N8N_WEBHOOK_URL, json=n8n_payload)
        response.raise_for_status()
        n8n_response_data = response.json()
        data_to_process = n8n_response_data.get('json', n8n_response_data)
        final_data = { "reply": data_to_process.get('reply') or data_to_process.get('output') }
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
        
    prompt_messages = messages + [{"role": "system", "content": "Summarize the following chat session in 5 words or less for a sidebar label."}]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo", messages=prompt_messages, max_tokens=20
        )
        summary = response.choices[0].message.content.strip().replace('"', '')
        return jsonify({"summary": summary})
        
    except Exception as e:
        print(f"Error calling OpenAI for summary: {e}")
        return jsonify({"summary": "Could not summarize."}), 500

# NEW: This endpoint calls OpenAI directly to get suggested replies
@app.route('/api/suggestions', methods=['POST'])
def get_suggestions():
    """
    Generates suggested replies for the conversation using the OpenAI API directly.
    """
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key not configured."}), 500

    data = request.json
    messages = data.get('messages', [])
    if len(messages) < 2: # Don't generate suggestions at the very start
        return jsonify({"suggestions": []})

    # Define a "tool" for the OpenAI API to force it to return structured JSON
    tools = [{
        "type": "function",
        "function": {
            "name": "show_suggested_replies",
            "description": "Show the user a few short suggested replies to continue the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "replies": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "An array of 3 short, relevant, and engaging replies based on the last message."
                    }
                },
                "required": ["replies"]
            }
        }
    }]

    try:
        # Call OpenAI API with a tool choice to force it to generate suggestions
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "show_suggested_replies"}}
        )
        
        choice = response.choices[0].message
        suggestions = []
        if choice.tool_calls:
            tool_call = choice.tool_calls[0]
            if tool_call.function.name == "show_suggested_replies":
                # The arguments are a JSON string, so we need to parse them
                arguments = json.loads(tool_call.function.arguments)
                suggestions = arguments.get('replies', [])
        
        return jsonify({"suggestions": suggestions})

    except Exception as e:
        print(f"Error generating suggestions with OpenAI: {e}")
        return jsonify({"suggestions": []}), 500


if __name__ == '__main__':
    # This is for local development. In production, Gunicorn will be used.
    app.run(host='0.0.0.0', port=5000, debug=True)
