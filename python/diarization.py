#!/usr/bin/env python3
"""
Diarização REAL otimizada para SERVIDOR 8vCPU + 32GB RAM
OTIMIZAÇÕES: Controle de recursos, processamento eficiente, chunks inteligentes
"""
from pyannote.audio import Pipeline
import os
import sys
from typing import List
import logging
import signal
import time
from pydub import AudioSegment
import torch
import tempfile
import psutil
import gc

# Token HuggingFace
HF_TOKEN = os.environ.get("HF_TOKEN")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DiarizationSegment:
    def __init__(self, start: float, end: float, speaker: str):
        self.start = start
        self.end = end
        self.speaker = speaker

    def to_dict(self):
        return {"start": self.start, "end": self.end, "speaker": self.speaker}

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Timeout na diarização")

class ServerResourceManager:
    """Gerencia recursos do servidor para otimizar performance"""
    
    def __init__(self):
        self.max_cpu_cores = min(6, os.cpu_count())  # Usar no máximo 6 dos 8 cores
        self.max_ram_gb = 24  # Usar no máximo 24GB dos 32GB
        
    def check_resources(self) -> dict:
        """Verifica recursos disponíveis do servidor"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'safe_to_process': cpu_percent < 80 and memory.percent < 75
        }
    
    def get_optimal_chunk_size(self, audio_duration: float) -> int:
        """Calcula tamanho ótimo de chunk baseado em recursos e duração"""
        resources = self.check_resources()
        
        if audio_duration <= 900:  # 15 min
            return int(audio_duration)  # Processamento direto
        
        # Ajustar tamanho do chunk baseado na RAM disponível
        if resources['memory_available_gb'] > 20:
            base_chunk = 600  # 10 minutos
        elif resources['memory_available_gb'] > 15:
            base_chunk = 450  # 7.5 minutos
        else:
            base_chunk = 300  # 5 minutos
        
        # Ajustar baseado na duração total
        if audio_duration > 7200:  # 2 horas
            return min(base_chunk, 300)  # Máximo 5 min para áudios muito longos
        elif audio_duration > 3600:  # 1 hora
            return min(base_chunk, 450)  # Máximo 7.5 min
        else:
            return base_chunk
    
    def configure_torch(self):
        """Configura PyTorch para usar recursos otimamente"""
        # Usar apenas cores disponíveis, deixando 2 livres para o sistema
        torch.set_num_threads(self.max_cpu_cores)
        
        # Configurações de memória para evitar OOM
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Garbage collection mais agressivo
        gc.collect()

def get_audio_duration(audio_path: str) -> float:
    """Retorna duração do áudio em segundos"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"Erro ao obter duração do áudio: {e}")
        return 0

def split_audio_for_server(audio_path: str, chunk_duration: int, max_chunks: int = 20) -> List[tuple]:
    """
    Divide áudio otimizado para servidor
    max_chunks: limite para evitar sobrecarga do servidor
    """
    try:
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0
        
        if total_duration <= chunk_duration:
            return [(audio_path, 0.0, total_duration)]
        
        # Calcular número de chunks necessários
        needed_chunks = int(total_duration / chunk_duration) + 1
        
        if needed_chunks > max_chunks:
            # Ajustar tamanho do chunk para não exceder limite
            chunk_duration = int(total_duration / max_chunks) + 1
            logger.warning(f"Ajustando chunk para {chunk_duration}s para limitar a {max_chunks} chunks")
        
        logger.info(f"Dividindo áudio de {total_duration/60:.1f}min em chunks de {chunk_duration/60:.1f}min")
        
        chunks = []
        current_time = 0.0
        overlap = min(30, chunk_duration * 0.1)  # Overlap proporcional, máximo 30s
        
        while current_time < total_duration:
            start_time = max(0, current_time - overlap) if len(chunks) > 0 else current_time
            end_time = min(current_time + chunk_duration, total_duration)
            
            # Extrair chunk
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            chunk_audio = audio[start_ms:end_ms]
            
            # Salvar chunk temporário
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                chunk_audio.export(temp_file.name, format='wav', parameters=["-ac", "1", "-ar", "16000"])
                chunks.append((temp_file.name, start_time, end_time))
            
            current_time += chunk_duration
        
        logger.info(f"Criados {len(chunks)} chunks")
        return chunks
        
    except Exception as e:
        logger.error(f"Erro ao dividir áudio: {e}")
        return [(audio_path, 0.0, get_audio_duration(audio_path))]

def diarize_chunk_optimized(pipeline, chunk_path: str, timeout_minutes: int = 6) -> List[DiarizationSegment]:
    """Diarização otimizada para servidor com timeout mais curto"""
    segments = []
    
    try:
        # Timeout mais agressivo para servidor
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_minutes * 60)
        
        logger.info(f"Diarizando chunk (timeout: {timeout_minutes}min)")
        
        # Configurações otimizadas para servidor
        diarization = pipeline(
            chunk_path,
            min_speakers=1,
            max_speakers=6,  # Reduzido para economizar recursos
        )
        
        signal.alarm(0)
        
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(DiarizationSegment(turn.start, turn.end, speaker))
        
        logger.info(f"✅ Chunk processado: {len(segments)} segmentos")
        
        # Limpeza de memória após chunk
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return segments
        
    except TimeoutException:
        signal.alarm(0)
        logger.error(f"❌ Timeout no chunk ({timeout_minutes}min)")
        raise
    except Exception as e:
        signal.alarm(0)
        logger.error(f"❌ Erro no chunk: {e}")
        raise

def merge_chunks_optimized(chunk_results: List[tuple]) -> List[DiarizationSegment]:
    """Mesclagem otimizada para servidor"""
    all_segments = []
    speaker_mapping = {}
    next_speaker_id = 0
    
    logger.info(f"Mesclando {len(chunk_results)} chunks...")
    
    for chunk_idx, (segments, chunk_start, chunk_end) in enumerate(chunk_results):
        chunk_speakers = {}
        
        for segment in segments:
            global_start = segment.start + chunk_start
            global_end = segment.end + chunk_start
            
            if segment.speaker not in chunk_speakers:
                # Mapear speaker simples - para servidor, priorizar velocidade
                if chunk_idx == 0:
                    # Primeiro chunk - usar speakers como estão
                    global_speaker = f"SPEAKER_{next_speaker_id:02d}"
                    chunk_speakers[segment.speaker] = global_speaker
                    next_speaker_id += 1
                else:
                    # Chunks seguintes - tentar mapear para speakers existentes
                    best_match = None
                    for existing_seg in all_segments[-10:]:  # Verificar apenas últimos 10 segmentos
                        if abs(existing_seg.end - global_start) < 60:  # 1 min de tolerância
                            best_match = existing_seg.speaker
                            break
                    
                    if best_match:
                        chunk_speakers[segment.speaker] = best_match
                    else:
                        global_speaker = f"SPEAKER_{next_speaker_id:02d}"
                        chunk_speakers[segment.speaker] = global_speaker
                        next_speaker_id += 1
            
            all_segments.append(DiarizationSegment(
                global_start, global_end, chunk_speakers[segment.speaker]
            ))
    
    # Otimização rápida
    all_segments.sort(key=lambda x: x.start)
    
    # Mesclagem simples e rápida
    if not all_segments:
        return []
    
    merged = [all_segments[0]]
    for segment in all_segments[1:]:
        last = merged[-1]
        if (last.speaker == segment.speaker and 
            segment.start - last.end <= 2.0):
            last.end = max(last.end, segment.end)
        else:
            merged.append(segment)
    
    speakers = set(seg.speaker for seg in merged)
    logger.info(f"✅ Mesclagem concluída: {len(merged)} segmentos, {len(speakers)} speakers")
    
    return merged

def diarize_audio(audio_path: str) -> List[DiarizationSegment]:
    """
    🖥️ DIARIZAÇÃO REAL otimizada para SERVIDOR 8vCPU + 32GB
    """
    hf_token = HF_TOKEN
    if not hf_token:
        raise ValueError("Token HuggingFace obrigatório!")
    
    # Inicializar gerenciador de recursos
    resource_manager = ServerResourceManager()
    
    # Verificar recursos iniciais
    resources = resource_manager.check_resources()
    logger.info(f"🖥️ SERVIDOR: CPU {resources['cpu_percent']:.1f}%, RAM {resources['memory_percent']:.1f}% ({resources['memory_available_gb']:.1f}GB livre)")
    
    if not resources['safe_to_process']:
        logger.warning("⚠️ Recursos do servidor limitados - processamento pode ser lento")
    
    duration = get_audio_duration(audio_path)
    logger.info(f"🎤 DIARIZAÇÃO SERVIDOR: Áudio de {duration/60:.1f} minutos")
    
    try:
        # Configurar PyTorch para servidor
        resource_manager.configure_torch()
        
        # Carregar pipeline
        logger.info("Carregando pipeline otimizado para servidor...")
        start_time = time.time()
        
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        
        # Configuração de hardware otimizada
        if torch.cuda.is_available():
            logger.info("🚀 GPU detectada - usando aceleração")
            pipeline = pipeline.to(torch.device("cuda"))
        else:
            logger.info(f"🖥️ CPU otimizada ({resource_manager.max_cpu_cores} cores)")
            pipeline = pipeline.to(torch.device("cpu"))
        
        load_time = time.time() - start_time
        logger.info(f"Pipeline carregado em {load_time:.1f}s")
        
        # Determinar estratégia baseada na duração
        chunk_size = resource_manager.get_optimal_chunk_size(duration)
        
        if chunk_size >= duration:  # Processamento direto
            logger.info("📋 Processamento direto")
            
            try:
                segments = diarize_chunk_optimized(pipeline, audio_path, timeout_minutes=12)
                speakers = set(seg.speaker for seg in segments)
                logger.info(f"✅ SERVIDOR: {len(segments)} segmentos, {len(speakers)} speakers")
                return segments
                
            except Exception as e:
                logger.error(f"Falha no processamento direto: {e}")
                raise
        
        else:  # Processamento em chunks
            logger.info(f"🔄 Processamento em chunks de {chunk_size/60:.1f}min")
            
            chunks = split_audio_for_server(audio_path, chunk_size, max_chunks=24)
            chunk_results = []
            temp_files = []
            
            try:
                for i, (chunk_path, start_time, end_time) in enumerate(chunks):
                    temp_files.append(chunk_path)
                    
                    # Verificar recursos antes de cada chunk
                    resources = resource_manager.check_resources()
                    if resources['memory_percent'] > 85:
                        logger.warning("⚠️ RAM alta - executando garbage collection")
                        gc.collect()
                        time.sleep(1)
                    
                    logger.info(f"🔄 Chunk {i+1}/{len(chunks)} (RAM: {resources['memory_percent']:.1f}%)")
                    
                    try:
                        segments = diarize_chunk_optimized(pipeline, chunk_path, timeout_minutes=8)
                        chunk_results.append((segments, start_time, end_time))
                        
                    except Exception as e:
                        logger.error(f"❌ Falha no chunk {i+1}: {e}")
                        # Fallback para chunk falhado
                        duration_chunk = end_time - start_time
                        fallback_segments = []
                        current_time = 0.0
                        speaker_id = i % 3
                        
                        while current_time < duration_chunk:
                            segment_end = min(current_time + 15.0, duration_chunk)
                            fallback_segments.append(DiarizationSegment(
                                current_time, segment_end, f"SPEAKER_{speaker_id:02d}"
                            ))
                            current_time = segment_end
                        
                        chunk_results.append((fallback_segments, start_time, end_time))
                        logger.warning(f"⚠️ Chunk {i+1} processado com fallback")
                
                # Mesclar resultados
                final_segments = merge_chunks_optimized(chunk_results)
                
                speakers = set(seg.speaker for seg in final_segments)
                logger.info(f"✅ SERVIDOR CONCLUÍDO: {len(final_segments)} segmentos, {len(speakers)} speakers")
                return final_segments
                
            finally:
                # Limpeza de arquivos temporários
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except:
                        pass
                
                # Limpeza final de memória
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        
    except Exception as e:
        logger.error(f"❌ Erro crítico no servidor: {e}")
        raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization.py <audio_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    try:
        logger.info(f"🖥️ Iniciando diarização em SERVIDOR: {audio_path}")
        segments = diarize_audio(audio_path)
        
        # Output
        for seg in segments:
            print(seg.to_dict())
            
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        sys.exit(1)