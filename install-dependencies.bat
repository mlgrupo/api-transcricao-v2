@echo off
echo Installing Python dependencies for transcription...
python -m pip install --upgrade pip
python -m pip install -r python/requirements.txt
echo Done!
