# PyTerminal

A simple Python-based terminal clone with a safe Flask web UI.  
Built for **SRM Hacks with CodeMate**.

## 🚀 Features
- Custom terminal commands (`ls`, `pwd`, `cat`, `mkdir`, `rm`, `ps`, `sys`)
- Cross-platform (Windows & Linux)
- History, quick command buttons, copy/download output
- Secure: only allowlisted commands are supported

---

## 💻 Run locally

1. Clone the repo:
   ```bash
   git clone https://github.com/sivaram-vinod/Python-Based-Command-Terminal.git
   cd pyterminal-hack


## Create and activate virtual environment:
python -m venv venv
# Windows PowerShell
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

## Install dependencies
pip install -r requirements.txt

## Run the app
python web_app/app.py

## Open the app in your browser
http://127.0.0.1:5000
