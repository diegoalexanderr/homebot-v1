from flask import Flask, render_template, request, jsonify
import requests
import os
import openai
import uuid  # <-- New import for generating unique IDs

app = Flask(__name__)

# Fetch environment variables for n8n and OpenAI
N8N_WEBHOOK_URL = os.environ['N8N_WEBHOOK_URL']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
openai.api_key = OPENAI_API_KEY

@app.route('/')
def index():
    """Renders the main page."""
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    """
    Handles incoming user messages, generates a session ID,
    forwards the message to an n8n webhook, and returns the bot's reply.
    """
    data = request.json
    # Handle the case where the JSON data might be an array
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    user_message = data.get('message')

    if not user_message:
        return jsonify({'reply': 'No message received.'}), 400

    # Generate a new, random session ID on the server
    session_id = str(uuid.uuid4())

    # Forward message and the new session ID to the n8n webhook
    try:
        response = requests.post(N8N_WEBHOOK_URL, json={
            'message': user_message,
            'sessionID': session_id # <-- Passing the newly generated session ID
        })
        response.raise_for_status() # Raise an exception for bad status codes
        bot_reply = response.json().get('output', 'No reply from webhook.')
        
        # Return the bot's reply and the new session ID to the client
        return jsonify({'reply': bot_reply, 'sessionID': session_id})

    except requests.exceptions.RequestException as e:
        # Handle any errors during the webhook request
        print(f"Error sending message to n8n: {e}")
        return jsonify({'reply': 'Failed to get a response from the webhook.'}), 500


@app.route('/summarize_session', methods=['POST'])
def summarize_session():
    """
    Summarizes a chat session using the OpenAI API.
    """
    data = request.json
    messages = data.get('messages', [])
    if not messages:
        return jsonify({"summary": "No messages to summarize."}), 400
    
    # Construct the prompt for the summarization
    prompt = "Summarize the following chat session in one short sentence for a sidebar label:\n" + "\n".join(messages)
    
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.choices[0].message.content.strip()
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"summary": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
