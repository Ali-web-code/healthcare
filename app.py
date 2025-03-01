from flask import Flask, render_template_string, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os
import speech_recognition as sr
import tempfile
from gtts import gTTS
import base64

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Healthcare Assistant</title>
    <style>
        /* Mobile-friendly styles */
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(to right, #00c6ff, #0072ff);
            color: #fff;
            padding: 20px;
        }

        .container {
            max-width: 500px;
            margin: 0 auto;
            background: #fff;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            padding: 20px;
            color: #333;
        }

        .header {
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 20px;
        }

        .chat-area {
            margin-bottom: 20px;
            padding: 10px;
            max-height: 400px;
            overflow-y: auto;
        }

        .message {
            padding: 10px;
            border-radius: 10px;
            margin: 5px 0;
        }

        .user-message {
            background: #e0f7fa;
            align-self: flex-start;
        }

        .bot-message {
            background: #f1f8e9;
            align-self: flex-end;
        }

        .button-group {
            display: flex;
            gap: 10px;
            justify-content: center;
        }

        button {
            padding: 10px 20px;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        #recordBtn {
            background-color: #25d366;
            color: #fff;
        }

        #playBtn {
            background-color: #128C7E;
            color: #fff;
        }

        button:hover {
            opacity: 0.8;
            transform: scale(1.05);
        }

        .hidden {
            display: none;
        }

        .disclaimer {
            font-size: 12px;
            text-align: center;
            margin-top: 10px;
            color: #777;
        }

        .input-area {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 20px;
        }

        #symptomInput {
            padding: 10px;
            width: 70%;
            border-radius: 25px;
            border: 1px solid #ccc;
            outline: none;
        }

        #symptomInput:focus {
            border-color: #0072ff;
        }

        select {
            padding: 10px;
            border-radius: 25px;
            border: 1px solid #ccc;
        }
    </style>
</head>
<body>

    <div class="container">
        <div class="header">AI-Healthcare Assistant</div>
        <div class="chat-area">
            {% if symptom %}
                <div class="message user-message">{{ symptom|e }}</div>
                <div class="message bot-message">
                    {{ advice|e }}
                    <button id="playBtn" class="hidden">▶ Play</button>
                </div>
            {% else %}
                <div class="message bot-message">Hello! Describe your symptoms by voice or text.</div>
            {% endif %}
        </div>

        <div class="disclaimer">
            Note: AI-powered assistant. Consult a real doctor for medical advice.
        </div>

        <form action="/" method="POST" class="input-area">
            <input type="text" name="symptom" id="symptomInput" placeholder="Type or speak your symptom..." required>
            <select name="language" id="languageSelect">
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <!-- Add other languages as needed -->
            </select>
            <div class="button-group">
                <button type="button" id="recordBtn">🎤 Record</button>
                <button type="submit">Send</button>
            </div>
        </form>

        <audio id="audioPlayer" hidden></audio>
    </div>

    <script>
        let mediaRecorder, audioChunks = [];
        let currentAudio = null;

        // Speech Recognition
        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                
                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'recording.wav');
                    
                    try {
                        const response = await fetch('/transcribe', {
                            method: 'POST',
                            body: formData
                        });
                        const data = await response.json();
                        if (data.text) {
                            document.getElementById('symptomInput').value = data.text;
                        }
                    } catch (error) {
                        console.error('Transcription error:', error);
                    }
                    
                    audioChunks = [];
                    stream.getTracks().forEach(track => track.stop());
                };
                
                mediaRecorder.start();
                document.getElementById('recordBtn').classList.add('recording');
            } catch (error) {
                alert('Microphone access required for voice input');
            }
        }

        // Text-to-Speech
        function playAudio(audioData) {
            const audioBlob = new Blob([Uint8Array.from(atob(audioData), c => c.charCodeAt(0))], { type: 'audio/mpeg' });
            const audioUrl = URL.createObjectURL(audioBlob);
            const audioPlayer = document.getElementById('audioPlayer');
            audioPlayer.src = audioUrl;
            audioPlayer.play();
        }

        document.getElementById('recordBtn').addEventListener('click', () => {
            if (!mediaRecorder || mediaRecorder.state === 'inactive') {
                startRecording();
                document.getElementById('recordBtn').textContent = '⏹ Stop';
            } else {
                mediaRecorder.stop();
                document.getElementById('recordBtn').textContent = '🎤 Record';
                document.getElementById('recordBtn').classList.remove('recording');
            }
        });

        {% if advice %}
            // Show play button and handle audio
            document.getElementById('playBtn').classList.remove('hidden');
            document.getElementById('playBtn').addEventListener('click', () => {
                playAudio('{{ audio_base64 }}');
            });
        {% endif %}
    </script>

</body>
</html>
'''

def transcribe_audio(audio_file):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError:
            return "Speech service error"

def text_to_speech(text):
    tts = gTTS(text=text, lang='en')
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
        tts.save(temp_file.name)
        with open(temp_file.name, 'rb') as f:
            audio_bytes = f.read()
    return base64.b64encode(audio_bytes).decode('utf-8')

@app.route('/transcribe', methods=['POST'])
def handle_transcription():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file received'}), 400
    
    audio_file = request.files['audio']
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        audio_file.save(temp_file.name)
        text = transcribe_audio(temp_file.name)
    
    return jsonify({'text': text})

@app.route('/', methods=['GET', 'POST'])
def health_chat():
    symptom = ''
    advice = ''
    audio_base64 = ''
    
    if request.method == 'POST':
        symptom = request.form.get('symptom', '').lower().strip()
        if symptom:
            advice = get_medical_advice(symptom)
            audio_base64 = text_to_speech(advice)
    
    return render_template_string(
        HTML_TEMPLATE,
        symptom=symptom,
        advice=advice,
        audio_base64=audio_base64
    )

def get_medical_advice(symptom):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a medical assistant. Provide brief, clear advice for symptoms. Include self-care tips and when to see a doctor. Keep responses under 100 words. Always remind to consult a real doctor."},
                {"role": "user", "content": f"I'm experiencing {symptom}. What should I do?"}
            ],
            temperature=0.3,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "Sorry, I'm having trouble processing your request. Please try again later."

if __name__ == '__main__':
    app.run(debug=True)