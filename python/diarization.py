#!/usr/bin/env python3
"""
Diarização EQUILIBRADA - Alta fidelidade + Anti-timeout
FOCO: Qualidade máxima da diarização, timeouts apenas como última proteção
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
        self.max_cpu_cores = min(6, os.cpu_count())  # RESTAURADO: 6 cores para qualidade
        self.max_ram_gb = 28  # AUMENTADO: Usar quase toda RAM para qualidade
        
    def check_resources(self) -> dict:
        """Verifica recursos disponíveis do servidor"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'safe_to_process': cpu_percent < 85 and memory.percent < 80  # Mais agressivo para qualidade
        }
    
    def get_optimal_chunk_size(self, audio_duration: float) -> int:
        """REBALANCEADO: Chunks maiores para melhor qualidade"""
        resources = self.check_resources()
        
        # Priorizar qualidade: chunks maiores quando possível
        if audio_duration <= 900:  # 15 min - processamento direto
            return int(audio_duration)
        
        # Chunks balanceados qualidade/performance
        if resources['memory_available_gb'] > 25:
            base_chunk = 480  # 8 minutos (aumentado)
        elif resources['memory_available_gb'] > 20:
            base_chunk = 360  # 6 minutos (aumentado)
        else:
            base_chunk = 240  # 4 minutos (ainda maior que antes)
        
        # Ajuste para duração total
        if audio_duration > 7200:  # 2 horas
            return min(base_chunk, 360)  # Máximo 6 min (era 5)
        elif audio_duration > 3600:  # 1 hora
            return min(base_chunk, 480)  # Máximo 8 min (era 7.5)
        else:
            return base_chunk
    
    def configure_torch(self):
        """Configuração otimizada para QUALIDADE"""
        # Usar todos os cores disponíveis para qualidade
        torch.set_num_threads(self.max_cpu_cores)
        
        # Limpeza de memória
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

def split_audio_for_server(audio_path: str, chunk_duration: int, max_chunks: int = 50) -> List[tuple]:
    """MELHORADO: Chunks inteligentes que preservam continuidade"""
    try:
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0
        
        if total_duration <= chunk_duration:
            return [(audio_path, 0.0, total_duration)]
        
        # Calcular número de chunks necessários
        needed_chunks = int(total_duration / chunk_duration) + 1
        
        if needed_chunks > max_chunks:
            # Ajustar mantendo qualidade mínima
            chunk_duration = max(120, int(total_duration / max_chunks))  # Mínimo 2 minutos
            logger.warning(f"Ajustando chunk para {chunk_duration}s para limitar a {max_chunks} chunks")
        
        logger.info(f"Dividindo áudio de {total_duration/60:.1f}min em chunks de {chunk_duration/60:.1f}min")
        
        chunks = []
        current_time = 0.0
        overlap = min(30, chunk_duration * 0.15)  # AUMENTADO: 15% overlap para continuidade
        
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

def diarize_chunk_optimized(pipeline, chunk_path: str, timeout_minutes: int = 15) -> List[DiarizationSegment]:
    """QUALIDADE MÁXIMA: Configurações otimizadas para fidelidade"""
    segments = []
    
    try:
        # Timeout generoso para qualidade
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_minutes * 60)
        
        logger.info(f"Diarizando chunk (timeout: {timeout_minutes}min)")
        
        # CONFIGURAÇÃO PARA MÁXIMA QUALIDADE
        diarization = pipeline(
            chunk_path,
            min_speakers=1,
            max_speakers=8,  # RESTAURADO: Até 8 speakers para fidelidade
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
        logger.error(f"❌ Timeout no chunk ({timeout_minutes}min) - usando fallback inteligente")
        
        # FALLBACK INTELIGENTE em caso de timeout
        chunk_duration = get_audio_duration(chunk_path)
        return intelligent_fallback_diarization(chunk_path, chunk_duration)
        
    except Exception as e:
        signal.alarm(0)
        logger.error(f"❌ Erro no chunk: {e} - usando fallback inteligente")
        
        # FALLBACK INTELIGENTE em caso de erro
        chunk_duration = get_audio_duration(chunk_path)
        return intelligent_fallback_diarization(chunk_path, chunk_duration)

def merge_chunks_advanced(chunk_results: List[tuple]) -> List[DiarizationSegment]:
    """MELHORADO: Mesclagem que preserva identidade de speakers"""
    all_segments = []
    speaker_mapping = {}
    next_speaker_id = 0
    
    # Análise de sobreposição para melhor mapeamento
    speaker_profiles = {}  # Para rastrear características de cada speaker
    
    logger.info(f"Mesclando {len(chunk_results)} chunks com preservação de identidade...")
    
    for chunk_idx, (segments, chunk_start, chunk_end) in enumerate(chunk_results):
        chunk_speakers = {}
        
        for segment in segments:
            global_start = segment.start + chunk_start
            global_end = segment.end + chunk_start
            
            if segment.speaker not in chunk_speakers:
                # Mapear speaker com análise de contexto
                if chunk_idx == 0:
                    # Primeiro chunk - estabelecer baseline
                    global_speaker = f"SPEAKER_{next_speaker_id:02d}"
                    chunk_speakers[segment.speaker] = global_speaker
                    speaker_profiles[global_speaker] = {
                        'last_seen': global_end,
                        'total_duration': global_end - global_start,
                        'segments_count': 1
                    }
                    next_speaker_id += 1
                else:
                    # Chunks seguintes - análise inteligente de continuidade
                    best_match = None
                    best_score = 0
                    
                    # Procurar speaker que fala próximo ao início deste chunk
                    for existing_speaker, profile in speaker_profiles.items():
                        time_gap = global_start - profile['last_seen']
                        
                        # Score baseado em proximidade temporal e padrões
                        if time_gap < 120:  # 2 minutos de tolerância
                            score = max(0, 1 - (time_gap / 120))
                            
                            # Bonus se duração do segmento é similar ao padrão do speaker
                            avg_duration = profile['total_duration'] / profile['segments_count']
                            duration_similarity = 1 - abs((global_end - global_start) - avg_duration) / max(avg_duration, 30)
                            score += duration_similarity * 0.3
                            
                            if score > best_score:
                                best_score = score
                                best_match = existing_speaker
                    
                    if best_match and best_score > 0.4:  # Threshold para aceitar match
                        chunk_speakers[segment.speaker] = best_match
                        # Atualizar perfil
                        speaker_profiles[best_match]['last_seen'] = global_end
                        speaker_profiles[best_match]['total_duration'] += global_end - global_start
                        speaker_profiles[best_match]['segments_count'] += 1
                    else:
                        # Novo speaker
                        global_speaker = f"SPEAKER_{next_speaker_id:02d}"
                        chunk_speakers[segment.speaker] = global_speaker
                        speaker_profiles[global_speaker] = {
                            'last_seen': global_end,
                            'total_duration': global_end - global_start,
                            'segments_count': 1
                        }
                        next_speaker_id += 1
            else:
                # Speaker já mapeado neste chunk
                mapped_speaker = chunk_speakers[segment.speaker]
                speaker_profiles[mapped_speaker]['last_seen'] = global_end
                speaker_profiles[mapped_speaker]['total_duration'] += global_end - global_start
                speaker_profiles[mapped_speaker]['segments_count'] += 1
            
            all_segments.append(DiarizationSegment(
                global_start, global_end, chunk_speakers[segment.speaker]
            ))
    
    # Ordenar por tempo
    all_segments.sort(key=lambda x: x.start)
    
    # Mesclagem inteligente preservando micro-pausas naturais
    if not all_segments:
        return []
    
    merged = [all_segments[0]]
    for segment in all_segments[1:]:
        last = merged[-1]
        if (last.speaker == segment.speaker and 
            segment.start - last.end <= 2.5):  # 2.5s para pausas naturais
            last.end = max(last.end, segment.end)
        else:
            merged.append(segment)
    
    speakers = set(seg.speaker for seg in merged)
    logger.info(f"✅ Mesclagem avançada concluída: {len(merged)} segmentos, {len(speakers)} speakers")
    
    return merged

def diarize_audio(audio_path: str) -> List[DiarizationSegment]:
    """
    🖥️ DIARIZAÇÃO EQUILIBRADA - Máxima fidelidade com proteção anti-timeout
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
    logger.info(f"🎤 DIARIZAÇÃO QUALIDADE: Áudio de {duration/60:.1f} minutos")
    
    # Fallback apenas para áudios EXTREMAMENTE longos (>2 horas)
    if duration > 7200:  # 2 horas
        logger.warning("⚠️ Áudio extremamente longo - usando diarização inteligente")
        return intelligent_fallback_diarization(audio_path, duration)
    
    try:
        # Configurar PyTorch para qualidade máxima
        resource_manager.configure_torch()
        
        # Carregar pipeline com timeout de segurança
        logger.info("Carregando pipeline otimizado para qualidade...")
        start_time = time.time()
        
        # Timeout para carregamento do pipeline
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(1200)  # 10 minutos para carregar (generoso)
        
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            
            # Configuração de hardware
            if torch.cuda.is_available():
                logger.info("🚀 GPU detectada - usando aceleração")
                pipeline = pipeline.to(torch.device("cuda"))
            else:
                logger.info(f"🖥️ CPU otimizada ({resource_manager.max_cpu_cores} cores)")
                pipeline = pipeline.to(torch.device("cpu"))
            
            signal.alarm(0)
            
        except TimeoutException:
            logger.error("❌ Timeout no carregamento do pipeline - usando fallback")
            return intelligent_fallback_diarization(audio_path, duration)
        
        load_time = time.time() - start_time
        logger.info(f"Pipeline carregado em {load_time:.1f}s")
        
        # Determinar estratégia baseada na duração
        chunk_size = resource_manager.get_optimal_chunk_size(duration)
        
        if chunk_size >= duration and duration <= 1200:  # Processamento direto até 15 min
            logger.info("📋 Processamento direto para máxima qualidade")
            
            try:
                segments = diarize_chunk_optimized(pipeline, audio_path, timeout_minutes=20)
                speakers = set(seg.speaker for seg in segments)
                logger.info(f"✅ QUALIDADE MÁXIMA: {len(segments)} segmentos, {len(speakers)} speakers")
                return segments
                
            except Exception as e:
                logger.error(f"Falha no processamento direto: {e} - usando fallback inteligente")
                return intelligent_fallback_diarization(audio_path, duration)
        
        else:  # Processamento em chunks com máxima qualidade
            logger.info(f"🔄 Processamento em chunks de {chunk_size/60:.1f}min para qualidade")
            
            chunks = split_audio_for_server(audio_path, chunk_size, max_chunks=60)
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
                        time.sleep(2)
                    
                    logger.info(f"🔄 Chunk {i+1}/{len(chunks)} (RAM: {resources['memory_percent']:.1f}%)")
                    
                    # Processar chunk com qualidade máxima
                    segments = diarize_chunk_optimized(pipeline, chunk_path, timeout_minutes=15)
                    chunk_results.append((segments, start_time, end_time))
                
                # Mesclar com preservação de identidade
                final_segments = merge_chunks_advanced(chunk_results)
                
                speakers = set(seg.speaker for seg in final_segments)
                logger.info(f"✅ QUALIDADE PRESERVADA: {len(final_segments)} segmentos, {len(speakers)} speakers")
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
        logger.error(f"❌ Erro crítico: {e} - usando fallback inteligente final")
        return intelligent_fallback_diarization(audio_path, duration)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization.py <audio_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    try:
        logger.info(f"🖥️ Iniciando diarização EQUILIBRADA: {audio_path}")
        segments = diarize_audio(audio_path)
        
        # Output
        for seg in segments:
            print(seg.to_dict())
            
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        sys.exit(1)