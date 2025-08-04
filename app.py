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

# This endpoint now calls OpenAI directly for summarization and a dynamic emoji
@app.route('/api/summarize', methods=['POST'])
def summarize():
    """
    Summarizes a chat session by calling the OpenAI API directly, requesting
    both a summary and a relevant emoji.
    """
    if not OPENAI_API_KEY:
        return jsonify({"summary": "OpenAI API key not configured."}), 500
    
    data = request.json
    messages = data.get('messages', [])
    if not messages:
        return jsonify({"summary": "No messages to summarize."}), 400
        
    tools = [{
        "type": "function",
        "function": {
            "name": "format_summary_with_emoji",
            "description": "Formats the session summary with a title and a single relevant emoji.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": { "type": "string", "description": "A short summary of the conversation, 5 words or less." },
                    "emoji": { "type": "string", "description": "A single emoji that best represents the topic." }
                },
                "required": ["summary", "emoji"]
            }
        }
    }]
    
    prompt_messages = messages + [{"role": "system", "content": "Summarize the conversation and provide a relevant emoji."}]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=prompt_messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "format_summary_with_emoji"}}
        )
        
        choice = response.choices[0].message
        summary = "Could not summarize."
        emoji = "✨" 

        if choice.tool_calls:
            tool_call = choice.tool_calls[0]
            if tool_call.function.name == "format_summary_with_emoji":
                arguments = json.loads(tool_call.function.arguments)
                summary = arguments.get('summary', summary)
                emoji = arguments.get('emoji', emoji)
        
        return jsonify({"summary": summary, "emoji": emoji})
        
    except Exception as e:
        print(f"Error calling OpenAI for summary: {e}")
        return jsonify({"summary": "Could not summarize.", "emoji": "✨"}), 500

# This endpoint calls OpenAI directly to get suggested replies
@app.route('/api/suggestions', methods=['POST'])
def get_suggestions():
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key not configured."}), 500

    data = request.json
    messages = data.get('messages', [])
    if len(messages) < 2:
        return jsonify({"suggestions": []})

    tools = [{
        "type": "function",
        "function": {
            "name": "show_suggested_replies",
            "description": "Show the user a few short suggested replies to continue the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "replies": { "type": "array", "items": { "type": "string" }, "description": "An array of 3 short, relevant, and engaging replies." }
                },
                "required": ["replies"]
            }
        }
    }]

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "show_suggested_replies"}}
        )
        
        choice = response.choices[0].message
        suggestions = []
        if choice.tool_calls:
            tool_call = choice.tool_calls[0]
            if tool_call.function.name == "show_suggested_replies":
                arguments = json.loads(tool_call.function.arguments)
                suggestions = arguments.get('replies', [])
        
        return jsonify({"suggestions": suggestions})

    except Exception as e:
        print(f"Error generating suggestions with OpenAI: {e}")
        return jsonify({"suggestions": []}), 500

# Endpoint for the Smart Context sidebar
@app.route('/api/context', methods=['POST'])
def get_context():
    """
    Analyzes the conversation to extract key entities and notes for the sidebar.
    """
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key not configured."}), 500

    data = request.json
    messages = data.get('messages', [])
    if len(messages) < 2:
        return jsonify({"entities": [], "notes": []})

    tools = [{
        "type": "function",
        "function": {
            "name": "format_context_and_notes",
            "description": "Extract key entities and create summary notes from a conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "term": {"type": "string", "description": "The key person, place, or concept."},
                                "definition": {"type": "string", "description": "A brief, one-sentence definition."}
                            }
                        },
                        "description": "A list of up to 3 key entities mentioned in the conversation."
                    },
                    "notes": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "A list of up to 3 key takeaways or important points to remember, phrased as short notes."
                    }
                },
                "required": ["entities", "notes"]
            }
        }
    }]
    
    prompt_messages = messages + [{"role": "system", "content": "Analyze the conversation. Extract key entities (people, places, concepts) and create a short list of key takeaways or notes. If no specific entities or notes are present, return empty arrays."}]

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=prompt_messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "format_context_and_notes"}}
        )
        choice = response.choices[0].message
        if choice.tool_calls:
            tool_call = choice.tool_calls[0]
            if tool_call.function.name == "format_context_and_notes":
                arguments = json.loads(tool_call.function.arguments)
                return jsonify(arguments)
        
        return jsonify({"entities": [], "notes": []})

    except Exception as e:
        print(f"Error generating context with OpenAI: {e}")
        return jsonify({"entities": [], "notes": []}), 500

# NEW: Endpoint to summarize selected text and add it to notes
@app.route('/api/summarize-selection', methods=['POST'])
def summarize_selection():
    """
    Receives a piece of selected text and summarizes it into a concise note.
    """
    if not OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key not configured."}), 500

    data = request.json
    selected_text = data.get('text', '')
    if not selected_text:
        return jsonify({"note": ""}), 400
    
    prompt = f"Condense the following text into a single, concise note that captures the main point. The note should be suitable for a 'Key Notes' list.\n\nText: \"{selected_text}\"\n\nNote:"

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        note = response.choices[0].message.content.strip()
        return jsonify({"note": note})
    except Exception as e:
        print(f"Error summarizing selection: {e}")
        return jsonify({"error": "Failed to summarize selection."}), 500

if __name__ == '__main__':
    # This is for local development. In production, Gunicorn will be used.
    app.run(host='0.0.0.0', port=5000, debug=True)
