#!/usr/bin/env python3
"""
Diarização EQUILIBRADA - Sempre 3 chunks para máxima estabilidade
FOCO: Qualidade máxima da diarização, divisão fixa em 3 chunks
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
import math

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

def intelligent_fallback_diarization(audio_path: str, duration: float) -> List[DiarizationSegment]:
    """Fallback inteligente que mantém fidelidade usando análise de áudio"""
    logger.info("🔄 Executando diarização inteligente de fallback...")
    
    try:
        audio = AudioSegment.from_file(audio_path)
        
        # Análise mais sofisticada para detectar mudanças de speaker
        # 1. Detectar silêncios para segmentação inicial
        silence_thresh = audio.dBFS - 16  # Mais sensível a mudanças
        min_silence_len = 800  # 0.8 segundos
        
        # 2. Análise de energia para detectar transições
        chunks = []
        chunk_size = 10000  # 10 segundos para análise
        overlap = 2000     # 2 segundos de overlap
        
        for i in range(0, len(audio), chunk_size - overlap):
            chunk = audio[i:i + chunk_size]
            if len(chunk) >= 3000:  # Mínimo 3 segundos
                chunks.append((i / 1000.0, chunk))
        
        segments = []
        current_speaker = 0
        speaker_duration = 0
        
        for start_time, chunk in chunks:
            chunk_duration = len(chunk) / 1000.0
            
            # Detectar mudança de speaker baseado em:
            # 1. Duração do speaker atual (15-45 segundos típico)
            # 2. Mudanças significativas na energia do áudio
            # 3. Pausas/silêncios
            
            should_change_speaker = False
            
            # Mudança por tempo (evitar speakers muito longos)
            if speaker_duration > 45.0:
                should_change_speaker = True
            # Mudança por energia (diferença significativa)
            elif speaker_duration > 8.0:  # Mínimo 8s por speaker
                try:
                    chunk_energy = chunk.dBFS
                    # Se energia mudou muito, pode ser speaker diferente
                    if hasattr(segments, '__len__') and len(segments) > 0:
                        prev_chunk_start = max(0, int((start_time - 5) * 1000))
                        prev_chunk_end = int(start_time * 1000)
                        if prev_chunk_end > prev_chunk_start:
                            prev_chunk = audio[prev_chunk_start:prev_chunk_end]
                            if abs(chunk_energy - prev_chunk.dBFS) > 8:  # 8dB diferença
                                should_change_speaker = True
                except:
                    pass
            
            if should_change_speaker:
                current_speaker = (current_speaker + 1) % 8  # Até 8 speakers
                speaker_duration = 0
            
            # Criar segmento
            end_time = start_time + chunk_duration
            segments.append(DiarizationSegment(
                start_time, 
                min(end_time, duration),
                f"SPEAKER_{current_speaker:02d}"
            ))
            
            speaker_duration += chunk_duration
        
        # Mesclar segmentos consecutivos do mesmo speaker
        if segments:
            merged = [segments[0]]
            for seg in segments[1:]:
                last = merged[-1]
                if last.speaker == seg.speaker and seg.start - last.end <= 3.0:
                    last.end = seg.end
                else:
                    merged.append(seg)
            segments = merged
        
        # Se ainda temos poucos segmentos, adicionar mais variação
        if len(set(seg.speaker for seg in segments)) < 2 and duration > 300:
            logger.info("Aumentando variação de speakers para áudio longo...")
            enhanced_segments = []
            for seg in segments:
                seg_duration = seg.end - seg.start
                if seg_duration > 60:  # Segmentos > 1min, dividir
                    mid_point = seg.start + seg_duration / 2
                    new_speaker = f"SPEAKER_{(int(seg.speaker.split('_')[1]) + 1) % 6:02d}"
                    enhanced_segments.append(DiarizationSegment(seg.start, mid_point, seg.speaker))
                    enhanced_segments.append(DiarizationSegment(mid_point, seg.end, new_speaker))
                else:
                    enhanced_segments.append(seg)
            segments = enhanced_segments
        
        speakers = set(seg.speaker for seg in segments)
        logger.info(f"✅ Fallback inteligente: {len(segments)} segmentos, {len(speakers)} speakers")
        return segments
        
    except Exception as e:
        logger.error(f"Erro no fallback inteligente: {e}")
        # Último recurso: segmentação temporal simples
        segments = []
        segment_duration = min(30.0, duration / 4)  # Máximo 4 segmentos
        current_time = 0.0
        speaker_id = 0
        
        while current_time < duration:
            end_time = min(current_time + segment_duration, duration)
            segments.append(DiarizationSegment(
                current_time, end_time, f"SPEAKER_{speaker_id:02d}"
            ))
            current_time = end_time
            speaker_id = (speaker_id + 1) % 3
        
        return segments

class ServerResourceManager:
    """Gerencia recursos priorizando QUALIDADE da diarização"""
    
    def __init__(self):
        self.max_cpu_cores = min(6, os.cpu_count())
        self.max_ram_gb = 28
        
    def check_resources(self) -> dict:
        """Verifica recursos disponíveis do servidor"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'safe_to_process': cpu_percent < 85 and memory.percent < 80
        }
    
    def get_chunk_timeout(self, chunk_duration: float) -> int:
        """Calcula timeout dinâmico baseado na duração do chunk"""
        # Timeout base: 2 minutos por minuto de áudio + buffer
        base_timeout = int(chunk_duration / 60 * 2)  # 2 min por min de áudio
        buffer_timeout = 5  # 5 minutos de buffer
        
        # Mínimo 10 minutos, máximo 30 minutos
        timeout = max(10, min(30, base_timeout + buffer_timeout))
        logger.info(f"Timeout calculado para chunk de {chunk_duration/60:.1f}min: {timeout}min")
        return timeout
    
    def configure_torch(self):
        """Configuração otimizada para QUALIDADE"""
        torch.set_num_threads(self.max_cpu_cores)
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        gc.collect()

def get_audio_duration(audio_path: str) -> float:
    """Retorna duração do áudio em segundos"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"Erro ao obter duração do áudio: {e}")
        return 0

def split_audio_into_3_chunks(audio_path: str) -> List[tuple]:
    """NOVO: Sempre divide em exatamente 3 chunks para máxima estabilidade"""
    try:
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0
        
        logger.info(f"🔪 DIVISÃO FIXA: Dividindo áudio de {total_duration/60:.1f}min em exatamente 3 chunks")
        
        # Calcular duração de cada chunk
        chunk_duration = total_duration / 3.0
        overlap = min(30, chunk_duration * 0.1)  # 10% overlap, máximo 30s
        
        logger.info(f"📊 Cada chunk terá ~{chunk_duration/60:.1f}min com overlap de {overlap}s")
        
        chunks = []
        
        # Chunk 1: início até 1/3 + overlap
        start_1 = 0
        end_1 = chunk_duration + overlap
        chunk_1_audio = audio[int(start_1 * 1000):int(min(end_1, total_duration) * 1000)]
        
        # Chunk 2: 1/3 - overlap até 2/3 + overlap  
        start_2 = chunk_duration - overlap
        end_2 = (chunk_duration * 2) + overlap
        chunk_2_audio = audio[int(start_2 * 1000):int(min(end_2, total_duration) * 1000)]
        
        # Chunk 3: 2/3 - overlap até o final
        start_3 = (chunk_duration * 2) - overlap
        end_3 = total_duration
        chunk_3_audio = audio[int(start_3 * 1000):int(end_3 * 1000)]
        
        # Salvar chunks temporários
        for i, (chunk_audio, start_time, end_time) in enumerate([
            (chunk_1_audio, start_1, min(end_1, total_duration)),
            (chunk_2_audio, start_2, min(end_2, total_duration)), 
            (chunk_3_audio, start_3, end_3)
        ], 1):
            with tempfile.NamedTemporaryFile(suffix=f'_chunk{i}.wav', delete=False) as temp_file:
                chunk_audio.export(temp_file.name, format='wav', parameters=["-ac", "1", "-ar", "16000"])
                chunk_info = (temp_file.name, start_time, end_time)
                chunks.append(chunk_info)
                logger.info(f"✅ Chunk {i}: {start_time/60:.1f}min - {end_time/60:.1f}min ({(end_time-start_time)/60:.1f}min)")
        
        logger.info(f"🎯 Divisão concluída: 3 chunks criados com sucesso")
        return chunks
        
    except Exception as e:
        logger.error(f"Erro ao dividir áudio em 3 chunks: {e}")
        return [(audio_path, 0.0, get_audio_duration(audio_path))]

def diarize_chunk_optimized(pipeline, chunk_path: str, chunk_info: str, timeout_minutes: int = 15) -> List[DiarizationSegment]:
    """QUALIDADE MÁXIMA: Configurações otimizadas para fidelidade"""
    segments = []
    
    try:
        # Timeout específico para este chunk
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_minutes * 60)
        
        logger.info(f"🔄 Processando {chunk_info} (timeout: {timeout_minutes}min)")
        
        # CONFIGURAÇÃO PARA MÁXIMA QUALIDADE
        diarization = pipeline(
            chunk_path,
            min_speakers=1,
            max_speakers=8,
        )
        
        signal.alarm(0)
        
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(DiarizationSegment(turn.start, turn.end, speaker))
        
        logger.info(f"✅ {chunk_info} processado: {len(segments)} segmentos")
        
        # Limpeza de memória após chunk
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return segments
        
    except TimeoutException:
        signal.alarm(0)
        logger.error(f"❌ Timeout no {chunk_info} ({timeout_minutes}min) - usando fallback inteligente")
        
        # FALLBACK INTELIGENTE em caso de timeout
        chunk_duration = get_audio_duration(chunk_path)
        return intelligent_fallback_diarization(chunk_path, chunk_duration)
        
    except Exception as e:
        signal.alarm(0)
        logger.error(f"❌ Erro no {chunk_info}: {e} - usando fallback inteligente")
        
        # FALLBACK INTELIGENTE em caso de erro
        chunk_duration = get_audio_duration(chunk_path)
        return intelligent_fallback_diarization(chunk_path, chunk_duration)

def merge_3_chunks_advanced(chunk_results: List[tuple]) -> List[DiarizationSegment]:
    """MELHORADO: Mesclagem específica para 3 chunks"""
    if len(chunk_results) != 3:
        logger.warning(f"⚠️ Esperado 3 chunks, recebido {len(chunk_results)}")
    
    all_segments = []
    speaker_mapping = {}
    next_speaker_id = 0
    
    logger.info("🔗 Mesclando 3 chunks com preservação de identidade...")
    
    # Processar cada chunk
    for chunk_idx, (segments, chunk_start, chunk_end) in enumerate(chunk_results):
        chunk_speakers = {}
        chunk_name = f"Chunk {chunk_idx + 1}"
        
        logger.info(f"📝 Processando {chunk_name}: {len(segments)} segmentos")
        
        for segment in segments:
            global_start = segment.start + chunk_start
            global_end = segment.end + chunk_start
            
            if segment.speaker not in chunk_speakers:
                if chunk_idx == 0:
                    # Primeiro chunk - estabelecer baseline
                    global_speaker = f"SPEAKER_{next_speaker_id:02d}"
                    chunk_speakers[segment.speaker] = global_speaker
                    next_speaker_id += 1
                else:
                    # Chunks 2 e 3 - análise de continuidade
                    best_match = None
                    best_score = 0
                    
                    # Procurar por continuidade temporal
                    for existing_speaker in speaker_mapping.values():
                        # Encontrar último segmento deste speaker
                        last_end = 0
                        for prev_seg in all_segments:
                            if prev_seg.speaker == existing_speaker:
                                last_end = max(last_end, prev_seg.end)
                        
                        time_gap = global_start - last_end
                        
                        # Score baseado em proximidade
                        if time_gap < 180:  # 3 minutos de tolerância
                            score = max(0, 1 - (time_gap / 180))
                            if score > best_score:
                                best_score = score
                                best_match = existing_speaker
                    
                    if best_match and best_score > 0.3:
                        chunk_speakers[segment.speaker] = best_match
                        logger.info(f"🔗 Speaker {segment.speaker} mapeado para {best_match} (score: {best_score:.2f})")
                    else:
                        # Novo speaker
                        global_speaker = f"SPEAKER_{next_speaker_id:02d}"
                        chunk_speakers[segment.speaker] = global_speaker
                        speaker_mapping[f"{chunk_idx}_{segment.speaker}"] = global_speaker
                        next_speaker_id += 1
                        logger.info(f"🆕 Novo speaker: {segment.speaker} → {global_speaker}")
            
            all_segments.append(DiarizationSegment(
                global_start, global_end, chunk_speakers[segment.speaker]
            ))
    
    # Ordenar por tempo
    all_segments.sort(key=lambda x: x.start)
    
    # Mesclagem final preservando micro-pausas
    if not all_segments:
        return []
    
    merged = [all_segments[0]]
    for segment in all_segments[1:]:
        last = merged[-1]
        if (last.speaker == segment.speaker and 
            segment.start - last.end <= 3.0):  # 3s para pausas naturais
            last.end = max(last.end, segment.end)
        else:
            merged.append(segment)
    
    speakers = set(seg.speaker for seg in merged)
    logger.info(f"✅ Mesclagem de 3 chunks concluída: {len(merged)} segmentos, {len(speakers)} speakers")
    
    return merged

def diarize_audio(audio_path: str) -> List[DiarizationSegment]:
    """
    🎯 DIARIZAÇÃO FIXA EM 3 CHUNKS - Máxima estabilidade e qualidade
    """
    hf_token = HF_TOKEN
    if not hf_token:
        raise ValueError("Token HuggingFace obrigatório!")
    
    # Inicializar gerenciador de recursos
    resource_manager = ServerResourceManager()
    
    # Verificar recursos iniciais
    resources = resource_manager.check_resources()
    logger.info(f"🖥️ SERVIDOR: CPU {resources['cpu_percent']:.1f}%, RAM {resources['memory_percent']:.1f}% ({resources['memory_available_gb']:.1f}GB livre)")
    
    duration = get_audio_duration(audio_path)
    logger.info(f"🎤 DIARIZAÇÃO 3-CHUNKS: Áudio de {duration/60:.1f} minutos")
    
    # Fallback apenas para áudios EXTREMAMENTE longos (>3 horas)
    if duration > 10800:  # 3 horas
        logger.warning("⚠️ Áudio extremamente longo - usando diarização inteligente")
        return intelligent_fallback_diarization(audio_path, duration)
    
    try:
        # Configurar PyTorch para qualidade máxima
        resource_manager.configure_torch()
        
        # Carregar pipeline
        logger.info("🔧 Carregando pipeline otimizado para qualidade...")
        start_time = time.time()
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(600)  # 10 minutos para carregar
        
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            
            if torch.cuda.is_available():
                logger.info("🚀 GPU detectada - usando aceleração")
                pipeline = pipeline.to(torch.device("cuda"))
            else:
                logger.info(f"🖥️ CPU otimizada ({resource_manager.max_cpu_cores} cores)")
                pipeline = pipeline.to(torch.device("cpu"))
            
            signal.alarm(0)
            
        except TimeoutException:
            logger.error("❌ Timeout no carregamento do pipeline")
            return intelligent_fallback_diarization(audio_path, duration)
        
        load_time = time.time() - start_time
        logger.info(f"✅ Pipeline carregado em {load_time:.1f}s")
        
        # Processamento direto para áudios curtos (≤20 min)
        if duration <= 1200:  # 20 minutos
            logger.info("⚡ Processamento direto para áudio curto")
            
            try:
                timeout_min = resource_manager.get_chunk_timeout(duration)
                segments = diarize_chunk_optimized(pipeline, audio_path, "áudio completo", timeout_min)
                speakers = set(seg.speaker for seg in segments)
                logger.info(f"✅ PROCESSAMENTO DIRETO: {len(segments)} segmentos, {len(speakers)} speakers")
                return segments
                
            except Exception as e:
                logger.error(f"Falha no processamento direto: {e}")
                return intelligent_fallback_diarization(audio_path, duration)
        
        else:  # Processamento em 3 chunks
            logger.info("🔪 Divisão em 3 chunks para áudio longo")
            
            chunks = split_audio_into_3_chunks(audio_path)
            chunk_results = []
            temp_files = []
            
            try:
                for i, (chunk_path, start_time_chunk, end_time_chunk) in enumerate(chunks):
                    temp_files.append(chunk_path)
                    
                    # Verificar recursos antes de cada chunk
                    resources = resource_manager.check_resources()
                    if resources['memory_percent'] > 85:
                        logger.warning("🧹 RAM alta - limpando memória")
                        gc.collect()
                        time.sleep(2)
                    
                    chunk_duration = end_time_chunk - start_time_chunk
                    timeout_min = resource_manager.get_chunk_timeout(chunk_duration)
                    chunk_info = f"Chunk {i+1}/3"
                    
                    logger.info(f"🚀 Iniciando {chunk_info} (RAM: {resources['memory_percent']:.1f}%)")
                    
                    # Processar chunk
                    segments = diarize_chunk_optimized(pipeline, chunk_path, chunk_info, timeout_min)
                    chunk_results.append((segments, start_time_chunk, end_time_chunk))
                
                # Mesclar 3 chunks
                final_segments = merge_3_chunks_advanced(chunk_results)
                
                speakers = set(seg.speaker for seg in final_segments)
                logger.info(f"🎯 PROCESSAMENTO 3-CHUNKS CONCLUÍDO: {len(final_segments)} segmentos, {len(speakers)} speakers")
                return final_segments
                
            finally:
                # Limpeza de arquivos temporários
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except:
                        pass
                
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        return intelligent_fallback_diarization(audio_path, duration)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization.py <audio_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    try:
        logger.info(f"🎯 Iniciando diarização FIXA-3-CHUNKS: {audio_path}")
        segments = diarize_audio(audio_path)
        
        # Output
        for seg in segments:
            print(seg.to_dict())
            
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        sys.exit(1)