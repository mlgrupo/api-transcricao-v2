import os
import sys
import tempfile
import shutil
import json
import math
import torch
import whisper
import subprocess
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

# Configurações
MAX_CHUNKS = 8
MAX_CONCURRENT_CHUNKS = 2 # Limitar para máxima estabilidade em CPU
WHISPER_MODEL = "medium"

USE_TURBO = os.environ.get("WHISPER_TURBO", "0") == "1"

if USE_TURBO:
    from faster_whisper import WhisperModel
    TURBO_MODEL = None
else:
    import whisper
    TURBO_MODEL = None

def log(msg):
    print(f"[chunked_transcribe] {msg}", file=sys.stderr)

# Utilitário para extrair áudio do vídeo
def extract_audio(video_path, audio_path):
    log(f"Extraindo áudio de {video_path} para {audio_path}")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Utilitário para dividir áudio em chunks
def split_audio(audio_path, out_dir, max_chunks=MAX_CHUNKS):
    log(f"Dividindo áudio {audio_path} em até {max_chunks} partes...")
    audio = AudioSegment.from_wav(audio_path)
    duration_ms = len(audio)
    if duration_ms == 0:
        raise Exception("Áudio extraído está vazio!")
    chunk_length = math.ceil(duration_ms / max_chunks)
    chunk_paths = []
    for i in range(max_chunks):
        start = i * chunk_length
        end = min((i + 1) * chunk_length, duration_ms)
        if start >= end:
            break
        chunk = audio[start:end]
        chunk_path = os.path.join(out_dir, f"chunk_{i+1}.wav")
        chunk.export(chunk_path, format="wav")
        chunk_paths.append((chunk_path, start / 1000, end / 1000))
    if not chunk_paths:
        raise Exception("Nenhum chunk de áudio foi criado!")
    return chunk_paths

# Função para transcrever um chunk
def transcribe_chunk(chunk_path, start_sec, end_sec, model):
    log(f"Transcrevendo chunk {chunk_path} ({start_sec:.1f}s - {end_sec:.1f}s)...")
    try:
        if USE_TURBO:
            global TURBO_MODEL
            if TURBO_MODEL is None:
                TURBO_MODEL = WhisperModel("large-v2", device="cpu", compute_type="int8")
            segments, info = TURBO_MODEL.transcribe(chunk_path, beam_size=5, word_timestamps=True)
            segs = []
            for seg in segments:
                segs.append({
                    "start": float(seg.start) + start_sec,
                    "end": float(seg.end) + start_sec,
                    "text": seg.text.strip()
                })
            return {"segments": segs, "chunk": os.path.basename(chunk_path)}
        else:
            result = model.transcribe(chunk_path, word_timestamps=True, verbose=False, fp16=False)
            segments = []
            for seg in result.get("segments", []):
                segments.append({
                    "start": float(seg["start"]) + start_sec,
                    "end": float(seg["end"]) + start_sec,
                    "text": seg["text"].strip()
                })
            del result
            return {"segments": segments, "chunk": os.path.basename(chunk_path)}
    except Exception as e:
        log(f"Erro ao transcrever chunk {chunk_path}: {e}")
        return {"segments": [], "chunk": os.path.basename(chunk_path), "error": str(e)}

# Pipeline principal
def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Uso: python chunked_transcribe.py <video_path>", "segments": []}))
        sys.exit(1)
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(json.dumps({"error": f"Arquivo não encontrado: {video_path}", "segments": []}))
        sys.exit(1)

    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, "audio.wav")
    try:
        log("Iniciando extração de áudio...")
        extract_audio(video_path, audio_path)
        log("Áudio extraído. Apagando vídeo original para liberar espaço...")
        try:
            os.remove(video_path)
        except Exception as e:
            log(f"Não foi possível apagar vídeo: {e}")
        log("Dividindo áudio em chunks...")
        chunk_infos = split_audio(audio_path, temp_dir, MAX_CHUNKS)
        log(f"{len(chunk_infos)} chunks criados.")
        try:
            os.remove(audio_path)
        except Exception as e:
            log(f"Não foi possível apagar áudio: {e}")
        log("Carregando modelo Whisper...")
        if USE_TURBO:
            model = None  # handled in transcribe_chunk
            log("Modo TURBO: usando faster-whisper (large-v2, int8, CPU)")
        else:
            model = whisper.load_model(WHISPER_MODEL, device="cpu")
            torch.set_default_dtype(torch.float32)  # Forçar FP32
            log("Modelo Whisper padrão carregado.")
        log("Modelo carregado. Iniciando transcrição dos chunks...")
        results = []
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CHUNKS) as executor:
            futures = [executor.submit(transcribe_chunk, chunk_path, start, end, model) for chunk_path, start, end in chunk_infos]
            for future in as_completed(futures):
                res = future.result()
                results.append(res)
                try:
                    os.remove(os.path.join(temp_dir, res["chunk"]))
                except Exception:
                    pass
        all_segments = []
        for chunk_path, start, end in chunk_infos:
            for r in results:
                if r["chunk"] == os.path.basename(chunk_path):
                    all_segments.extend(r.get("segments", []))
        if not all_segments:
            raise Exception("Nenhum segmento de transcrição gerado!")
        print(json.dumps({"segments": all_segments}, ensure_ascii=False))
    except Exception as e:
        log(f"Erro fatal: {e}")
        print(json.dumps({"error": str(e), "segments": []}))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main() 