#!/usr/bin/env python3
"""
Sistema de Transcrição Ultra-Otimizado para Alta Performance
Configurado para: 7.5 vCPUs, 28GB RAM
"""
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
import psutil
import time
from typing import List, Tuple, Dict, Any

# Configurações otimizadas para 7.5 vCPUs e 28GB RAM
MAX_WORKERS = 8  # 8 workers para chunks menores (mais paralelização)
MAX_MEMORY_GB = 26  # 26GB para transcrição (deixa 2GB para sistema)
CHUNK_SIZE_MB = 30  # Tamanho ideal de chunk para processamento (reduzido)
MIN_CHUNK_SECONDS = 30  # Mínimo 30 segundos por chunk
MAX_CHUNK_SECONDS = 300  # Máximo 5 minutos por chunk
WHISPER_MODEL = "medium"  # Modelo mais rápido por padrão
USE_TURBO = os.environ.get("WHISPER_TURBO", "0") == "1"

# Configurações de qualidade - TODOS usando medium
QUALITY_CONFIGS = {
    "fast": {
        "model": "medium",
        "beam_size": 2,
        "best_of": 1,
        "temperature": 0.0,
        "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6
    },
    "balanced": {
        "model": "medium",
        "beam_size": 3,
        "best_of": 2,
        "temperature": 0.0,
        "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6
    },
    "high_quality": {
        "model": "medium",
        "beam_size": 5,
        "best_of": 3,
        "temperature": 0.0,
        "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6
    }
}

def log(msg: str, level: str = "INFO"):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", file=sys.stderr)

def get_optimal_config(duration_seconds: float) -> Dict[str, Any]:
    """Determina configuração ideal baseada na duração do áudio"""
    if duration_seconds < 300:  # < 5 minutos
        return QUALITY_CONFIGS["high_quality"]
    elif duration_seconds < 1800:  # < 30 minutos
        return QUALITY_CONFIGS["balanced"]
    elif duration_seconds < 3600:  # < 1 hora
        return QUALITY_CONFIGS["fast"]
    else:  # > 1 hora
        return QUALITY_CONFIGS["fast"]  # Sempre fast para vídeos muito longos

def get_optimal_chunk_size(duration_seconds: float) -> int:
    """Calcula tamanho ideal de chunk baseado na duração"""
    if duration_seconds < 300:  # < 5 minutos
        return min(duration_seconds, 300)  # Chunk único ou máximo 5 min
    elif duration_seconds < 1800:  # < 30 minutos
        return min(duration_seconds / 3, 400)  # 3 chunks ou máximo 6.7 min
    elif duration_seconds < 3600:  # < 1 hora
        return min(duration_seconds / 6, 350)  # 6 chunks ou máximo 10 min
    else:  # > 1 hora
        return min(duration_seconds / 12, 300)  # 12+ chunks ou máximo 5 min

def extract_audio(video_path: str, audio_path: str) -> None:
    """Extrai áudio otimizado para transcrição"""
    log(f"Extraindo áudio de {video_path}")
    
    # Configuração otimizada para transcrição
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",  # Sem vídeo
        "-acodec", "pcm_s16le",  # Codec PCM 16-bit
        "-ar", "16000",  # Sample rate 16kHz (ideal para Whisper)
        "-ac", "1",  # Mono
        "-af", "highpass=f=200,lowpass=f=8000,volume=1.5",  # Filtros de áudio
        audio_path
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        log("Áudio extraído com sucesso")
    except subprocess.CalledProcessError as e:
        log(f"Erro na extração de áudio: {e.stderr}", "ERROR")
        raise

def split_audio_optimized(audio_path: str, out_dir: str, duration_seconds: float) -> List[Tuple[str, float, float]]:
    """Divide áudio de forma otimizada"""
    log(f"Dividindo áudio em chunks otimizados (duração: {duration_seconds:.1f}s)")
    
    audio = AudioSegment.from_wav(audio_path)
    chunk_size_seconds = get_optimal_chunk_size(duration_seconds)
    
    # Calcular número de chunks
    n_chunks = max(1, math.ceil(duration_seconds / chunk_size_seconds))
    actual_chunk_size = duration_seconds / n_chunks
    
    log(f"Configuração: {n_chunks} chunks de ~{actual_chunk_size:.1f}s cada")
    
    chunk_paths = []
    start = 0
    
    for i in range(n_chunks):
        end = min(start + actual_chunk_size * 1000, len(audio))
        if i == n_chunks - 1:
            end = len(audio)  # Último chunk pega o resto
        
        if start >= end:
            break
            
        chunk = audio[int(start):int(end)]
        chunk_path = os.path.join(out_dir, f"chunk_{i+1:03d}.wav")
        
        # Otimizar chunk antes de salvar
        chunk = chunk.set_frame_rate(16000).set_channels(1)
        
        # Normalizar volume
        chunk = chunk.normalize()
        
        chunk.export(chunk_path, format="wav")
        chunk_paths.append((chunk_path, start / 1000, end / 1000))
        start = end
    
    log(f"Criados {len(chunk_paths)} chunks otimizados")
    return chunk_paths

def transcribe_chunk_optimized(chunk_info: Tuple[str, float, float], config: Dict[str, Any], total_chunks: int, chunk_index: int, model) -> Dict[str, Any]:
    """Transcreve um chunk com configuração otimizada"""
    chunk_path, start_sec, end_sec = chunk_info
    
    try:
        # Calcular porcentagem de progresso
        progress_percent = ((chunk_index + 1) / total_chunks) * 100
        log(f"Transcrevendo chunk {os.path.basename(chunk_path)} ({start_sec:.1f}s - {end_sec:.1f}s) - Progresso: {progress_percent:.1f}%")
        
        # Usar modelo já carregado (passado como parâmetro)
        # Configurações otimizadas para chunks menores
        result = model.transcribe(
            chunk_path,
            beam_size=config["beam_size"],
            best_of=config["best_of"],
            temperature=config["temperature"],
            compression_ratio_threshold=config["compression_ratio_threshold"],
            logprob_threshold=config["logprob_threshold"],
            no_speech_threshold=config["no_speech_threshold"],
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=None,
            verbose=False,
            fp16=False
        )
        
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": float(seg["start"]) + start_sec,
                "end": float(seg["end"]) + start_sec,
                "text": seg["text"].strip(),
                "words": seg.get("words", [])
            })
        
        # Log de conclusão do chunk
        log(f"Chunk {os.path.basename(chunk_path)} concluído - {len(segments)} segmentos - Progresso: {progress_percent:.1f}%")
        
        return {
            "segments": segments, 
            "chunk": os.path.basename(chunk_path),
            "language": result.get("language", "pt"),
            "language_probability": result.get("language_probability", 1.0),
            "progress_percent": progress_percent,
            "chunk_index": chunk_index
        }
        
    except Exception as e:
        log(f"Erro ao transcrever chunk {chunk_path}: {e}", "ERROR")
        return {
            "segments": [], 
            "chunk": os.path.basename(chunk_path), 
            "error": str(e),
            "progress_percent": ((chunk_index + 1) / total_chunks) * 100,
            "chunk_index": chunk_index
        }

def monitor_resources() -> Dict[str, float]:
    """Monitora uso de recursos"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available_gb": memory.available / (1024**3)
    }

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Uso: python chunked_transcribe.py <video_path>", "segments": []}))
        sys.exit(1)
    
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(json.dumps({"error": f"Arquivo não encontrado: {video_path}", "segments": []}))
        sys.exit(1)

    start_time = time.time()
    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, "audio.wav")
    
    try:
        # Monitor inicial
        resources = monitor_resources()
        log(f"Recursos iniciais: CPU {resources['cpu_percent']:.1f}%, RAM {resources['memory_percent']:.1f}% ({resources['memory_available_gb']:.1f}GB livre)")
        
        # Extrair áudio
        log("Iniciando extração de áudio...")
        extract_audio(video_path, audio_path)
        
        # Obter duração do áudio
        audio = AudioSegment.from_wav(audio_path)
        duration_seconds = len(audio) / 1000
        log(f"Duração do áudio: {duration_seconds:.1f} segundos")
        
        # Determinar configuração otimal
        config = get_optimal_config(duration_seconds)
        log(f"Configuração selecionada: {config['model']} (beam_size={config['beam_size']}, best_of={config['best_of']})")
        
        # Dividir áudio
        log("Dividindo áudio em chunks...")
        chunk_infos = split_audio_optimized(audio_path, temp_dir, duration_seconds)
        
        # Limpar áudio original para liberar espaço
        try:
            os.remove(audio_path)
            del audio
        except:
            pass
        
        # Transcrever chunks em paralelo
        log(f"Iniciando transcrição paralela com {MAX_WORKERS} workers...")
        
        # Carregar modelo UMA VEZ SÓ
        log("Carregando modelo Whisper medium...")
        model = whisper.load_model("medium", device="cpu")
        log("Modelo carregado com sucesso!")
        
        all_segments = []
        languages = []
        language_probs = []
        completed_chunks = 0
        start_transcription_time = time.time()
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submeter todos os chunks
            future_to_chunk = {
                executor.submit(transcribe_chunk_optimized, chunk_info, config, len(chunk_infos), i, model): chunk_info 
                for i, chunk_info in enumerate(chunk_infos)
            }
            
            # Processar resultados conforme ficam prontos
            for future in as_completed(future_to_chunk):
                chunk_info = future_to_chunk[future]
                try:
                    result = future.result()
                    completed_chunks += 1
                    
                    if "error" in result:
                        log(f"Erro no chunk {result['chunk']}: {result['error']}", "ERROR")
                        continue
                    
                    all_segments.extend(result.get("segments", []))
                    languages.append(result.get("language", "pt"))
                    language_probs.append(result.get("language_probability", 1.0))
                    
                    # Calcular progresso geral e tempo estimado
                    overall_progress = (completed_chunks / len(chunk_infos)) * 100
                    elapsed_time = time.time() - start_transcription_time
                    
                    if completed_chunks > 0:
                        avg_time_per_chunk = elapsed_time / completed_chunks
                        remaining_chunks = len(chunk_infos) - completed_chunks
                        estimated_remaining_time = remaining_chunks * avg_time_per_chunk
                        
                        log(f"Progresso geral: {overall_progress:.1f}% ({completed_chunks}/{len(chunk_infos)} chunks) - Tempo restante estimado: {estimated_remaining_time/60:.1f} min")
                    
                    # Monitorar recursos a cada 2 chunks completados
                    if completed_chunks % 2 == 0:
                        resources = monitor_resources()
                        log(f"Recursos: CPU {resources['cpu_percent']:.1f}%, RAM {resources['memory_percent']:.1f}% - Segmentos: {len(all_segments)}")
                    
                    # Limpar chunk processado
                    try:
                        os.remove(chunk_info[0])
                    except:
                        pass
                        
                except Exception as e:
                    log(f"Erro ao processar chunk {chunk_info[0]}: {e}", "ERROR")
        
        if not all_segments:
            raise Exception("Nenhum segmento de transcrição gerado!")
        
        # Limpar modelo da memória
        del model
        
        # Determinar idioma dominante
        if languages:
            dominant_language = max(set(languages), key=languages.count)
            avg_language_prob = sum(language_probs) / len(language_probs)
        else:
            dominant_language = "pt"
            avg_language_prob = 1.0
        
        # Ordenar segmentos por tempo
        all_segments.sort(key=lambda x: x["start"])
        
        # Estatísticas finais
        total_duration = time.time() - start_time
        total_text = " ".join([seg["text"] for seg in all_segments])
        
        log(f"Transcrição concluída em {total_duration:.1f}s")
        log(f"Segmentos: {len(all_segments)}, Caracteres: {len(total_text)}")
        log(f"Idioma: {dominant_language} (confiança: {avg_language_prob:.2f})")
        
        # Resultado final
        result = {
            "segments": all_segments,
            "metadata": {
                "duration_seconds": duration_seconds,
                "processing_time_seconds": total_duration,
                "segments_count": len(all_segments),
                "total_characters": len(total_text),
                "language": dominant_language,
                "language_confidence": avg_language_prob,
                "model_used": config["model"],
                "workers_used": MAX_WORKERS,
                "chunks_processed": len(chunk_infos)
            }
        }
        
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        log(f"Erro fatal: {e}", "ERROR")
        print(json.dumps({"error": str(e), "segments": []}))
    finally:
        # Limpeza final
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

if __name__ == "__main__":
    main() 