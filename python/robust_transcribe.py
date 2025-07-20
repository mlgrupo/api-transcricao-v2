#!/usr/bin/env python3
"""
Sistema de Transcrição Robusto e Otimizado
Combina velocidade e qualidade com processamento paralelo controlado
"""
import os
import sys
import tempfile
import shutil
import json
import time
import torch
import whisper
import subprocess
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import gc

# Configurações robustas e otimizadas
CHUNK_SIZE_SECONDS = 300  # 5 minutos por chunk
MAX_WORKERS = 2  # Processar 2 chunks por vez (robusto)
WHISPER_MODEL = "medium"  # Equilibrio entre velocidade e qualidade

# Configurações de qualidade por duração
QUALITY_CONFIGS = {
    "fast": {
        "model": "medium",
        "beam_size": 2,
        "best_of": 1,
        "temperature": 0.0,
        "patience": 1,
        "length_penalty": 1.0,
        "repetition_penalty": 1.0
    },
    "balanced": {
        "model": "medium", 
        "beam_size": 3,
        "best_of": 2,
        "temperature": 0.0,
        "patience": 2,
        "length_penalty": 1.0,
        "repetition_penalty": 1.0
    },
    "high_quality": {
        "model": "medium",
        "beam_size": 5,
        "best_of": 3,
        "temperature": 0.0,
        "patience": 3,
        "length_penalty": 1.0,
        "repetition_penalty": 1.0
    }
}

def log(msg: str, level: str = "INFO"):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", file=sys.stderr)

def get_optimal_config(duration_seconds: float) -> dict:
    """Determina configuração ideal baseada na duração"""
    if duration_seconds < 300:  # < 5 minutos
        return QUALITY_CONFIGS["high_quality"]
    elif duration_seconds < 1800:  # < 30 minutos
        return QUALITY_CONFIGS["balanced"]
    else:  # > 30 minutos
        return QUALITY_CONFIGS["fast"]

def monitor_resources() -> dict:
    """Monitora recursos do sistema"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available_gb": memory.available / (1024**3)
    }

def extract_audio_optimized(video_path: str, audio_path: str) -> None:
    """Extrai áudio com otimizações de velocidade"""
    log(f"Extraindo áudio de {video_path}")
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-af", "highpass=f=200,lowpass=f=8000,volume=1.5",
        "-threads", "8",
        "-preset", "ultrafast",
        "-loglevel", "error",
        audio_path
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        log("Áudio extraído com sucesso")
    except subprocess.CalledProcessError as e:
        log(f"Erro na extração de áudio: {e.stderr}", "ERROR")
        raise

def split_audio_optimized(audio_path: str, out_dir: str, duration_seconds: float) -> list:
    """Divide áudio em chunks otimizados"""
    log("Dividindo áudio em chunks otimizados")
    
    audio = AudioSegment.from_wav(audio_path)
    
    # Ajustar tamanho de chunk baseado na duração
    if duration_seconds < 600:  # < 10 minutos
        chunk_size = min(300, duration_seconds)  # Chunk único ou menor
    elif duration_seconds < 3600:  # < 1 hora
        chunk_size = 300  # 5 minutos
    else:  # > 1 hora
        chunk_size = 600  # 10 minutos para vídeos muito longos
    
    n_chunks = max(1, int(duration_seconds / chunk_size) + 1)
    log(f"Duração: {duration_seconds:.1f}s, Chunks: {n_chunks} de {chunk_size}s")
    
    chunk_paths = []
    start = 0
    
    for i in range(n_chunks):
        end = min(start + chunk_size * 1000, len(audio))
        if i == n_chunks - 1:
            end = len(audio)
        
        if start >= end:
            break
            
        chunk = audio[int(start):int(end)]
        chunk_path = os.path.join(out_dir, f"chunk_{i+1:03d}.wav")
        
        # Otimizações de áudio
        chunk = chunk.set_frame_rate(16000).set_channels(1)
        chunk = chunk.normalize()
        chunk = chunk.high_pass_filter(200)
        chunk = chunk.low_pass_filter(8000)
        
        chunk.export(chunk_path, format="wav", parameters=["-threads", "8", "-compression_level", "0"])
        
        chunk_paths.append((chunk_path, start / 1000, end / 1000))
        start = end
    
    log(f"Criados {len(chunk_paths)} chunks otimizados")
    return chunk_paths

def transcribe_chunk_robust(chunk_info: tuple, config: dict, total_chunks: int, chunk_index: int, model) -> dict:
    """Transcreve um chunk com configuração robusta"""
    chunk_path, start_sec, end_sec = chunk_info
    
    try:
        progress_percent = ((chunk_index + 1) / total_chunks) * 100
        log(f"Transcrevendo chunk {chunk_index + 1}/{total_chunks} ({progress_percent:.1f}%) - {start_sec:.1f}s a {end_sec:.1f}s")
        
        # Configurações robustas
        result = model.transcribe(
            chunk_path,
            beam_size=config["beam_size"],
            best_of=config["best_of"],
            temperature=config["temperature"],
            patience=config["patience"],
            length_penalty=config["length_penalty"],
            repetition_penalty=config["repetition_penalty"],
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=None,
            verbose=False,
            fp16=False,
            language="pt",
            task="transcribe",
            suppress_tokens=[-1],
            without_timestamps=False,
            max_initial_timestamp=1.0,
            prepend_punctuations="\"'([{-",
            append_punctuations="\"'.!?):]}",
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6
        )
        
        segments = []
        for seg in result.get("segments", []):
            segment_data = {
                "start": float(seg["start"]) + start_sec,
                "end": float(seg["end"]) + start_sec,
                "text": seg["text"].strip()
            }
            
            # Incluir timestamps das palavras
            if "words" in seg and seg["words"]:
                segment_data["words"] = []
                for word in seg["words"]:
                    word_data = {
                        "word": word["word"],
                        "start": float(word["start"]) + start_sec,
                        "end": float(word["end"]) + start_sec,
                        "probability": word.get("probability", 0.0)
                    }
                    segment_data["words"].append(word_data)
            
            segments.append(segment_data)
        
        log(f"Chunk {chunk_index + 1} concluído - {len(segments)} segmentos")
        
        # Limpeza de memória
        del result
        gc.collect()
        
        return {
            "segments": segments,
            "language": result.get("language", "pt"),
            "success": True
        }
        
    except Exception as e:
        log(f"Erro no chunk {chunk_index + 1}: {e}", "ERROR")
        return {
            "segments": [],
            "language": "pt",
            "success": False,
            "error": str(e)
        }

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Uso: python robust_transcribe.py <video_path>", "segments": []}))
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
        extract_audio_optimized(video_path, audio_path)
        
        # Obter duração
        audio = AudioSegment.from_wav(audio_path)
        duration_seconds = len(audio) / 1000
        log(f"Duração do áudio: {duration_seconds:.1f} segundos")
        
        # Determinar configuração otimal
        config = get_optimal_config(duration_seconds)
        log(f"Configuração selecionada: {config['model']} (beam_size={config['beam_size']}, best_of={config['best_of']})")
        
        # Dividir áudio
        log("Dividindo áudio em chunks...")
        chunk_infos = split_audio_optimized(audio_path, temp_dir, duration_seconds)
        
        # Limpar áudio original
        try:
            os.remove(audio_path)
            del audio
        except:
            pass
        
        # Carregar modelo UMA VEZ
        log(f"Carregando modelo Whisper {config['model']}...")
        model = whisper.load_model(config["model"], device="cpu")
        
        # Configurar PyTorch para performance
        torch.set_num_threads(8)
        torch.set_default_dtype(torch.float32)
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        torch.set_grad_enabled(False)
        
        if hasattr(model, 'encoder'):
            model.encoder.eval()
        if hasattr(model, 'decoder'):
            model.decoder.eval()
        
        log("Modelo carregado com sucesso!")
        
        # Transcrever chunks em paralelo (2 por vez)
        log(f"Iniciando transcrição paralela com {MAX_WORKERS} workers...")
        
        all_segments = []
        languages = []
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submeter todos os chunks
            future_to_chunk = {
                executor.submit(transcribe_chunk_robust, chunk_info, config, len(chunk_infos), i, model): i
                for i, chunk_info in enumerate(chunk_infos)
            }
            
            # Processar resultados conforme completam
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    result = future.result()
                    if result["success"]:
                        all_segments.extend(result["segments"])
                        languages.append(result["language"])
                    else:
                        log(f"Chunk {chunk_index + 1} falhou, continuando...", "WARNING")
                except Exception as e:
                    log(f"Erro no chunk {chunk_index + 1}: {e}", "ERROR")
                
                # Limpar chunk processado
                try:
                    chunk_path = chunk_infos[chunk_index][0]
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
                "chunks_processed": len(chunk_infos),
                "workers_used": MAX_WORKERS,
                "model_used": config["model"],
                "speed_factor": duration_seconds / total_duration
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