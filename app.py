from flask import Flask, render_template, request, jsonify
import requests
import os
import openai

app = Flask(__name__)

N8N_WEBHOOK_URL = os.environ['N8N_WEBHOOK_URL']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
openai.api_key = OPENAI_API_KEY

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    if isinstance(data, list) and len(data) > 0:
        data = data[0]
    user_message = data.get('message')
    session_id = data.get('sessionid')
    # Forward message to n8n webhook
    response = requests.post(N8N_WEBHOOK_URL, json={'message': user_message, 'sessionid': session_id})
    bot_reply = response.json().get('output', 'No reply from webhook.')
    return jsonify({'reply': bot_reply})

@app.route('/summarize_session', methods=['POST'])
def summarize_session():
    data = request.json
    messages = data.get('messages', [])
    if not messages:
        return jsonify({"summary": "No messages to summarize."}), 400
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
