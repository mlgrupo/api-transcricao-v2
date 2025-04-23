import sys
import json
import logging
import whisper
from text_processor import TextProcessor, TextProcessingRules
from pydub import AudioSegment
import os

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def basic_text_processor():
    rules = TextProcessingRules(
        capitalize_sentences=True,
        fix_spaces=True,
        ensure_final_punctuation=True,
        normalize_numbers=False,
        fix_common_errors=False,
        normalize_punctuation=True,
        capitalize_words=['Brasil', 'São Paulo', 'Rio de Janeiro'],
        common_replacements={}
    )
    return TextProcessor(rules)

def split_audio_streaming(file_path, chunk_duration_ms=5 * 60 * 1000):
    """Corta o áudio em blocos de X segundos."""
    audio = AudioSegment.from_file(file_path)

    for i in range(0, len(audio), chunk_duration_ms):
        chunk = audio[i:i + chunk_duration_ms]
        chunk_path = f"{file_path}_chunk_{i // chunk_duration_ms}.mp3"
        chunk.export(chunk_path, format="mp3")
        yield chunk_path

def transcribe_audio(audio_path):
    try:
        text_processor = basic_text_processor()
        model = whisper.load_model("large")  # Alterar para um modelo maior, se necessário

        full_text = ""
        chunk_count = 0

        for chunk_path in split_audio_streaming(audio_path):
            chunk_count += 1

            result = model.transcribe(
                chunk_path,
                language="pt",
                initial_prompt=(
                    "Transcreva em português do Brasil. "
                    "Use linguagem formal e evite redundâncias. "
                    "Corrija erros comuns e normalize números."
                )
            )

            processed = text_processor.process(result["text"])
            full_text += processed + "\n"

            try:
                os.remove(chunk_path)
            except Exception:
                pass

        return json.dumps({
            "status": "success",
            "text": full_text.strip(),
            "chunks": chunk_count,
            "language": "pt"
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stdout.buffer.write(json.dumps({
            "status": "error",
            "error": "Please provide the audio file path"
        }, ensure_ascii=False).encode('utf-8'))
        sys.exit(1)

    audio_path = sys.argv[1]
    output = transcribe_audio(audio_path)
    sys.stdout.buffer.write(output.encode('utf-8'))
