import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# --------------------- CONFIGURATION ---------------------

# Flask setup
app = Flask(__name__)
CORS(app)

# Gemini setup
genai.configure(api_key="AIzaSyDC2603M6IyhlYlGirpom8DpDFSlzyw5Hk")  # Replace with your Gemini API Key
model = genai.GenerativeModel(model_name="gemini-2.0-flash")

# Firebase setup
cred = credentials.Certificate("firebase_service_account.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Memory store
chat_sessions = {}  # Temporary session memory

# ---------------------- API ROUTES -----------------------

@app.route('/start_conversation', methods=['POST'])
def start_conversation():
    data = request.json
    user_id = data.get('user_id')
    topic = data.get('topic', 'General')

    # Start a new Gemini chat session
    chat = model.start_chat(history=[
        {"role": "user", "parts": f"You are my spoken English tutor and when I say anything wrong just correct me and let's have a conversation on the topic {topic} "}
    ])
    chat_sessions[user_id] = chat

    return jsonify({"message": "Chat started", "topic": topic})


@app.route('/continue_conversation', methods=['POST'])
def continue_conversation():
    data = request.json
    user_id = data.get('user_id')
    convo_id = data.get('convo_id')
    user_msg = data.get('message')
    topic = data.get('topic', 'General')

    # Get chat session
    if user_id not in chat_sessions:
        return jsonify({"error": "Chat session not found"}), 400

    chat = chat_sessions[user_id]

    # Send message to Gemini
    gemini_response = chat.send_message(user_msg)
    ai_reply = gemini_response.text
    ai_reply = re.sub(r"[^a-zA-Z\s,.!:0-9]", "", ai_reply)

    # Save chat to Firestore
    convo_ref = db.collection('users').document(user_id).collection('conversations').document(convo_id)
    convo_ref.set({
        'topic': topic,
        'timestamp': firestore.SERVER_TIMESTAMP
    }, merge=True)
    convo_ref.update({
        'messages': firestore.ArrayUnion([
            {'sender': 'user', 'text': user_msg,},
            {'sender': 'ai', 'text': ai_reply}
        ])
    })

    return jsonify({
        "ai_reply": ai_reply,
    })


@app.route('/get_conversation', methods=['POST'])
def get_conversation():
    data = request.json
    user_id = data.get('user_id')
    convo_id = data.get('convo_id')

    convo_ref = db.collection('users').document(user_id).collection('conversations').document(convo_id)
    doc = convo_ref.get()

    if doc.exists:
        return jsonify(doc.to_dict())
    else:
        return jsonify({"error": "Conversation not found"}), 404

@app.route('/get_summary', methods=['POST'])
def get_summary():
    data = request.json
    message = data.get('message')

    response = model.generate_content("{message} get me the summary of the conversation in 2 to 3 sentences ")

    if doc.exists:
        return jsonify({"summary": response})
    else:
        return jsonify({"error": "Conversation not found"}), 404
# ---------------------- MAIN -----------------------

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Get the PORT from env
    app.run(host='0.0.0.0', port=port)
