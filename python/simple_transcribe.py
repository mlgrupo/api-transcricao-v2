#!/usr/bin/env python3
"""
Transcrição Simples e Robusta
Processa um chunk por vez, sem erros
"""
import os
import sys
import tempfile
import shutil
import json
import whisper
import subprocess
from pydub import AudioSegment
import time

def log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", file=sys.stderr)

def extract_audio(video_path: str, audio_path: str) -> None:
    """Extrai áudio do vídeo"""
    log(f"Extraindo áudio de {video_path}")
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        log("Áudio extraído com sucesso")
    except subprocess.CalledProcessError as e:
        log(f"Erro na extração de áudio: {e.stderr}")
        raise

def split_audio_simple(audio_path: str, out_dir: str) -> list:
    """Divide áudio em chunks de 5 minutos"""
    log("Dividindo áudio em chunks de 5 minutos")
    
    audio = AudioSegment.from_wav(audio_path)
    duration_seconds = len(audio) / 1000
    
    # Chunks de 5 minutos (300 segundos)
    chunk_size_seconds = 300
    n_chunks = max(1, int(duration_seconds / chunk_size_seconds) + 1)
    
    log(f"Duração: {duration_seconds:.1f}s, Chunks: {n_chunks}")
    
    chunk_paths = []
    start = 0
    
    for i in range(n_chunks):
        end = min(start + chunk_size_seconds * 1000, len(audio))
        if i == n_chunks - 1:
            end = len(audio)  # Último chunk pega o resto
        
        if start >= end:
            break
            
        chunk = audio[int(start):int(end)]
        chunk_path = os.path.join(out_dir, f"chunk_{i+1:03d}.wav")
        
        # Normalizar e salvar
        chunk = chunk.set_frame_rate(16000).set_channels(1)
        chunk.export(chunk_path, format="wav")
        
        chunk_paths.append((chunk_path, start / 1000, end / 1000))
        start = end
    
    log(f"Criados {len(chunk_paths)} chunks")
    return chunk_paths

def transcribe_chunk_simple(chunk_path: str, start_sec: float, end_sec: float, model, chunk_num: int, total_chunks: int) -> dict:
    """Transcreve um chunk de forma simples"""
    try:
        progress = (chunk_num / total_chunks) * 100
        log(f"Transcrevendo chunk {chunk_num}/{total_chunks} ({progress:.1f}%) - {start_sec:.1f}s a {end_sec:.1f}s")
        
        # Transcrever com configurações simples
        result = model.transcribe(
            chunk_path,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            verbose=False,
            fp16=False
        )
        
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": float(seg["start"]) + start_sec,
                "end": float(seg["end"]) + start_sec,
                "text": seg["text"].strip()
            })
        
        log(f"Chunk {chunk_num} concluído - {len(segments)} segmentos")
        return {
            "segments": segments,
            "language": result.get("language", "pt"),
            "success": True
        }
        
    except Exception as e:
        log(f"Erro no chunk {chunk_num}: {e}")
        return {
            "segments": [],
            "language": "pt",
            "success": False,
            "error": str(e)
        }

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Uso: python simple_transcribe.py <video_path>", "segments": []}))
        sys.exit(1)
    
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(json.dumps({"error": f"Arquivo não encontrado: {video_path}", "segments": []}))
        sys.exit(1)

    start_time = time.time()
    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, "audio.wav")
    
    try:
        # Extrair áudio
        log("Iniciando extração de áudio...")
        extract_audio(video_path, audio_path)
        
        # Obter duração
        audio = AudioSegment.from_wav(audio_path)
        duration_seconds = len(audio) / 1000
        log(f"Duração do áudio: {duration_seconds:.1f} segundos")
        
        # Dividir áudio
        log("Dividindo áudio em chunks...")
        chunk_infos = split_audio_simple(audio_path, temp_dir)
        
        # Limpar áudio original
        try:
            os.remove(audio_path)
            del audio
        except:
            pass
        
        # Carregar modelo UMA VEZ
        log("Carregando modelo Whisper medium...")
        model = whisper.load_model("medium", device="cpu")
        log("Modelo carregado com sucesso!")
        
        # Transcrever chunks SEQUENCIALMENTE (um por vez)
        log(f"Iniciando transcrição sequencial de {len(chunk_infos)} chunks...")
        
        all_segments = []
        languages = []
        
        for i, (chunk_path, start_sec, end_sec) in enumerate(chunk_infos):
            chunk_num = i + 1
            result = transcribe_chunk_simple(chunk_path, start_sec, end_sec, model, chunk_num, len(chunk_infos))
            
            if result["success"]:
                all_segments.extend(result["segments"])
                languages.append(result["language"])
            else:
                log(f"Chunk {chunk_num} falhou, continuando...")
            
            # Limpar chunk processado
            try:
                os.remove(chunk_path)
            except:
                pass
        
        if not all_segments:
            raise Exception("Nenhum segmento de transcrição gerado!")
        
        # Determinar idioma dominante
        if languages:
            dominant_language = max(set(languages), key=languages.count)
        else:
            dominant_language = "pt"
        
        # Ordenar segmentos por tempo
        all_segments.sort(key=lambda x: x["start"])
        
        # Estatísticas finais
        total_duration = time.time() - start_time
        total_text = " ".join([seg["text"] for seg in all_segments])
        
        log(f"Transcrição concluída em {total_duration:.1f}s")
        log(f"Segmentos: {len(all_segments)}, Caracteres: {len(total_text)}")
        log(f"Idioma: {dominant_language}")
        
        # Resultado final
        result = {
            "segments": all_segments,
            "metadata": {
                "duration_seconds": duration_seconds,
                "processing_time_seconds": total_duration,
                "segments_count": len(all_segments),
                "total_characters": len(total_text),
                "language": dominant_language,
                "chunks_processed": len(chunk_infos)
            }
        }
        
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        log(f"Erro fatal: {e}")
        print(json.dumps({"error": str(e), "segments": []}))
    finally:
        # Limpeza final
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

if __name__ == "__main__":
    main() 