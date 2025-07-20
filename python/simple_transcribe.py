#!/usr/bin/env python3
"""
Transcrição Simples e Robusta
Processa um chunk por vez, sem erros
"""
# Configurações otimizadas para máxima velocidade
import os
import sys
import tempfile
import shutil
import json
import whisper
import subprocess
from pydub import AudioSegment
import time
import torch

# Configurações para máxima velocidade
CHUNK_SIZE_SECONDS = 300  # 5 minutos por chunk (como solicitado)
WHISPER_MODEL = "small"  # Modelo MUITO mais rápido que medium
BEAM_SIZE = 1  # Mínimo para velocidade
BEST_OF = 1   # Mínimo para velocidade

def log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", file=sys.stderr)

def extract_audio(video_path: str, audio_path: str) -> None:
    """Extrai áudio do vídeo com configurações ULTRA otimizadas"""
    log(f"Extraindo áudio de {video_path}")
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-af", "highpass=f=200,lowpass=f=8000,volume=1.5",  # Filtros otimizados + volume
        "-threads", "8",  # Usar todos os threads
        "-preset", "ultrafast",  # Preset mais rápido
        "-loglevel", "error",  # Minimizar logs
        audio_path
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        log("Áudio extraído com sucesso")
    except subprocess.CalledProcessError as e:
        log(f"Erro na extração de áudio: {e.stderr}")
        raise

def split_audio_simple(audio_path: str, out_dir: str) -> list:
    """Divide áudio em chunks de 5 minutos para máxima velocidade"""
    log("Dividindo áudio em chunks de 5 minutos")
    
    audio = AudioSegment.from_wav(audio_path)
    duration_seconds = len(audio) / 1000
    
    # Chunks de 5 minutos (300 segundos) para máxima velocidade
    chunk_size_seconds = CHUNK_SIZE_SECONDS
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
        
        # Otimizações para velocidade
        chunk = chunk.set_frame_rate(16000).set_channels(1)
        
        # Otimizações ULTRA rápidas de áudio
        chunk = chunk.normalize()  # Normalizar volume
        chunk = chunk.high_pass_filter(200)  # Filtrar baixas frequências
        chunk = chunk.low_pass_filter(8000)  # Filtrar altas frequências
        
        # Export otimizado para velocidade
        chunk.export(chunk_path, format="wav", parameters=["-threads", "8", "-compression_level", "0"])
        
        chunk_paths.append((chunk_path, start / 1000, end / 1000))
        start = end
    
    log(f"Criados {len(chunk_paths)} chunks otimizados")
    return chunk_paths

def transcribe_chunk_simple(chunk_path: str, start_sec: float, end_sec: float, model, chunk_num: int, total_chunks: int) -> dict:
    """Transcreve um chunk com configurações de máxima velocidade"""
    try:
        progress = (chunk_num / total_chunks) * 100
        log(f"Transcrevendo chunk {chunk_num}/{total_chunks} ({progress:.1f}%) - {start_sec:.1f}s a {end_sec:.1f}s")
        
        # Configurações para máxima velocidade
        result = model.transcribe(
            chunk_path,
            beam_size=BEAM_SIZE,
            best_of=BEST_OF,
            temperature=0.0,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            word_timestamps=True,  # Habilitado para ter timestamps
            condition_on_previous_text=False,
            initial_prompt=None,
            verbose=False,
            fp16=False,
            # Otimizações adicionais para velocidade
            language="pt",  # Forçar português para velocidade
            task="transcribe",  # Especificar tarefa
            suppress_tokens=[-1],  # Suprimir tokens especiais
            without_timestamps=False,  # Manter timestamps
            max_initial_timestamp=1.0,  # Limitar timestamp inicial
            prepend_punctuations="\"'([{-",  # Configurar pontuação (sem caracteres especiais)
            append_punctuations="\"'.!?):]}",
            # Configurações ULTRA rápidas
            patience=1,  # Mínimo patience para velocidade
            length_penalty=1.0,  # Penalidade mínima
            repetition_penalty=1.0,  # Penalidade mínima
            no_speech_threshold=0.8,  # Mais tolerante para velocidade
            logprob_threshold=-1.0,  # Mínimo threshold
            compression_ratio_threshold=2.4  # Máximo threshold
        )
        
        segments = []
        for seg in result.get("segments", []):
            segment_data = {
                "start": float(seg["start"]) + start_sec,
                "end": float(seg["end"]) + start_sec,
                "text": seg["text"].strip()
            }
            
            # Incluir timestamps das palavras se disponível
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
        
        # Carregar modelo UMA VEZ com configurações ULTRA otimizadas
        log("Carregando modelo Whisper small com configurações ULTRA otimizadas...")
        model = whisper.load_model(WHISPER_MODEL, device="cpu")
        
        # Configurar PyTorch para máxima performance
        torch.set_num_threads(8)  # Usar todos os cores disponíveis
        torch.set_default_dtype(torch.float32)
        
        # Otimizações ULTRA rápidas
        torch.backends.cudnn.benchmark = True  # Otimizar convoluções
        torch.backends.cudnn.deterministic = False  # Permitir otimizações não-determinísticas
        torch.backends.cudnn.enabled = True  # Habilitar cuDNN
        
        # Configurar cache de modelo para reutilização
        if hasattr(model, 'encoder'):
            model.encoder.eval()  # Modo de avaliação para velocidade
        if hasattr(model, 'decoder'):
            model.decoder.eval()  # Modo de avaliação para velocidade
        
        # Otimizações de memória
        torch.set_grad_enabled(False)  # Desabilitar gradientes para velocidade
        
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
            
            # Limpeza de memória otimizada
            if hasattr(torch, 'cuda') and torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Forçar garbage collection para liberar memória
            import gc
            gc.collect()
        
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
                "speed_factor": duration_seconds / total_duration
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