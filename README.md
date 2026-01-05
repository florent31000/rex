# 🐕 Rex-Brain

> Transform your Unitree Go2 Air robot into an intelligent, conversational companion using an Android phone as its "brain".

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Kivy](https://img.shields.io/badge/Kivy-2.3.0-orange.svg)](https://kivy.org/)

## 📖 Overview

Rex-Brain is an open-source project that uses an Asus Zenphone 8 (or similar Android device) mounted on a Unitree Go2 Air robot to create an interactive, intelligent robotic dog. The phone provides:
- **Vision** via its front camera
- **Hearing** via its microphone
- **Voice** via its speakers
- **Processing power** and **internet connectivity**

The robot receives high-level movement commands while all "thinking" is done through cloud APIs (LLM, speech-to-text, text-to-speech, vision analysis).

## ✨ Features

- 🗣️ **Natural conversation** - Responds when called by name, maintains context
- 👁️ **Person recognition** - Remembers faces and names of people it meets
- 🧠 **Long-term memory** - Recalls past conversations and events
- 🎭 **Configurable personality** - Witty, sarcastic, bold by default
- 🚶 **Autonomous behaviors** - Idle wandering, greeting people, following
- 🔋 **Battery awareness** - Warns when running low
- 🛑 **Emergency stop** - Voice command "STOP Rex" immediately stops all movement

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ANDROID PHONE (Zenphone 8)                │
├─────────────────────────────────────────────────────────────┤
│  PERCEPTION          COGNITION           ACTION             │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐        │
│  │ Camera   │──────►│ Context  │──────►│ Movement │        │
│  │ (faces)  │       │ Builder  │       │ Commands │        │
│  └──────────┘       └────┬─────┘       └──────────┘        │
│  ┌──────────┐            │             ┌──────────┐        │
│  │ Micro    │──────►┌────▼─────┐──────►│ TTS      │        │
│  │ (speech) │       │ LLM API  │       │ Speaker  │        │
│  └──────────┘       └──────────┘       └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│                         WebRTC                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Unitree Go2 Air │
                    └─────────────────┘
```

## 📋 Prerequisites

### Hardware
- **Unitree Go2 Air** robot
- **Android phone** (tested with Asus Zenphone 8, Android 11+)
- **3D-printed mount** to attach phone to robot's back
- **WiFi access** for internet connectivity

### Software (on your PC for development)
- Python 3.10+
- Buildozer (for Android APK building)
- Android SDK (installed automatically by Buildozer)

### Cloud Services (APIs required)
| Service | Purpose | Estimated Cost |
|---------|---------|----------------|
| **Deepgram** | Speech-to-text + diarization | ~$0.0043/min |
| **OpenAI** | Text-to-speech (TTS) | ~$0.015/1K chars |
| **Anthropic Claude** | LLM + Vision analysis | ~$3-15/M tokens |

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/rex-brain.git
cd rex-brain
```

### 2. Install dependencies (PC)
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API keys
```bash
cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml with your API keys
```

### 4. Build Android APK
```bash
# Install Buildozer
pip install buildozer

# Build APK (first build takes 30-60 minutes)
buildozer android debug
```

### 5. Install on phone
```bash
# Connect phone via USB with debugging enabled
buildozer android deploy run
```

## ⚙️ Configuration

### `config/settings.yaml`
```yaml
robot:
  name: "Rex"
  masters: ["Caroline", "Sam", "Florent"]
  
api_keys:
  deepgram: "your-key-here"
  openai: "your-key-here"
  anthropic: "your-key-here"

behavior:
  idle_walk_interval_min: 60  # seconds
  idle_walk_interval_max: 300
  scene_analysis_interval: 2.0  # seconds
  greeting_cooldown: 3600  # 1 hour before re-greeting same person
```

### `config/personality.yaml`
```yaml
traits:
  - witty
  - sarcastic
  - bold
  - politically_incorrect
  - playful

speaking_style: |
  You speak like a clever dog who gained human-level intelligence.
  You're loyal but not submissive. You have opinions and share them.
  You use humor, especially sarcasm. You're not afraid to tease people.
```

## 📱 Phone Setup

1. **Enable Developer Options** on your phone
2. **Enable USB Debugging**
3. **Connect to robot's WiFi** (Go2-XXXXXX network)
4. **Launch Rex-Brain app**
5. The app will automatically connect to the robot

## 🎮 Voice Commands

| Command | Action |
|---------|--------|
| "Rex" | Wake up and listen |
| "STOP Rex" | Emergency stop - lie down immediately |
| "Rex, follow me" | Enable follow mode |
| "Rex, sport mode" | Switch to sport mode |
| "Rex, go to sleep" | Lie down and enter idle mode |

## 🔧 Development

### Project Structure
```
rex/
├── config/                 # Configuration files
├── src/
│   ├── perception/        # Camera, microphone, vision
│   ├── cognition/         # LLM, memory, context
│   ├── action/            # Movement, speech, behaviors
│   ├── ui/                # Kivy interface
│   └── utils/             # Helpers
├── data/                  # Local databases
└── tests/                 # Unit tests
```

### Running tests
```bash
pytest tests/
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines first.

## ⚠️ Safety Notes

- Always supervise the robot when active
- Keep emergency stop command in mind ("STOP Rex")
- The robot will automatically stop if internet connection is lost
- Never use on stairs unless explicitly commanded

