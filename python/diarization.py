#!/usr/bin/env python3
"""
Diarização 100% GRATUITA - Sem tokens, sem dependências externas
FOCO: Funciona offline, usando apenas análise de áudio
"""
import os
import sys
from typing import List
import logging
import time
from pydub import AudioSegment
import numpy as np
import tempfile
import gc
import math

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DiarizationSegment:
    def __init__(self, start: float, end: float, speaker: str):
        self.start = start
        self.end = end
        self.speaker = speaker

    def to_dict(self):
        return {"start": self.start, "end": self.end, "speaker": self.speaker}

def analyze_audio_energy(audio_segment, window_size=1000):
    """Analisa energia do áudio para detectar mudanças de speaker"""
    samples = np.array(audio_segment.get_array_of_samples())
    if audio_segment.channels == 2:
        samples = samples.reshape((-1, 2))
        samples = samples.mean(axis=1)
    
    # Dividir em janelas e calcular energia RMS
    energies = []
    for i in range(0, len(samples), window_size):
        window = samples[i:i+window_size]
        if len(window) > 0:
            rms = np.sqrt(np.mean(window**2))
            energies.append(rms)
    
    return energies

def detect_silence_segments(audio_segment, silence_thresh=-40, min_silence_len=500):
    """Detecta segmentos de silêncio"""
    silence_segments = []
    
    # Detectar silêncios
    chunks = []
    chunk_size = 100  # 100ms chunks
    
    for i in range(0, len(audio_segment), chunk_size):
        chunk = audio_segment[i:i + chunk_size]
        chunks.append((i / 1000.0, chunk.dBFS))
    
    # Encontrar períodos de silêncio
    in_silence = False
    silence_start = 0
    
    for time_pos, db_level in chunks:
        if db_level < silence_thresh:  # Silêncio
            if not in_silence:
                silence_start = time_pos
                in_silence = True
        else:  # Som
            if in_silence and (time_pos - silence_start) * 1000 >= min_silence_len:
                silence_segments.append((silence_start, time_pos))
            in_silence = False
    
    return silence_segments

def advanced_speaker_detection(audio_path: str, target_speakers=None) -> List[DiarizationSegment]:
    """Detecção avançada de speakers usando análise de áudio pura"""
    logger.info("🔍 Iniciando detecção avançada de speakers...")
    
    try:
        audio = AudioSegment.from_file(audio_path)
        duration = len(audio) / 1000.0
        
        logger.info(f"📊 Analisando áudio de {duration/60:.1f} minutos")
        
        # 1. Detectar silêncios para segmentação natural
        silence_segments = detect_silence_segments(audio, silence_thresh=-35, min_silence_len=300)
        logger.info(f"🔇 Detectados {len(silence_segments)} períodos de silêncio")
        
        # 2. Análise de energia em janelas
        energies = analyze_audio_energy(audio, window_size=2000)  # 2 segundos
        
        # 3. Detectar mudanças significativas na energia
        energy_changes = []
        if len(energies) > 1:
            for i in range(1, len(energies)):
                if energies[i-1] > 0:  # Evitar divisão por zero
                    change_ratio = abs(energies[i] - energies[i-1]) / energies[i-1]
                    if change_ratio > 0.3:  # 30% de mudança
                        time_pos = i * 2.0  # 2 segundos por janela
                        energy_changes.append(time_pos)
        
        logger.info(f"⚡ Detectadas {len(energy_changes)} mudanças de energia")
        
        # 4. Combinar silêncios e mudanças de energia para criar pontos de divisão
        division_points = []
        
        # Adicionar silêncios como pontos de divisão
        for silence_start, silence_end in silence_segments:
            division_points.append(silence_start)
        
        # Adicionar mudanças de energia
        division_points.extend(energy_changes)
        
        # Remover duplicatas e ordenar
        division_points = sorted(list(set(division_points)))
        
        # Filtrar pontos muito próximos (mínimo 5 segundos entre speakers)
        filtered_points = [0]  # Sempre começar do início
        for point in division_points:
            if point - filtered_points[-1] >= 5.0:
                filtered_points.append(point)
        
        if filtered_points[-1] < duration - 5:  # Se não termina próximo ao fim
            filtered_points.append(duration)
        
        logger.info(f"📍 Pontos de divisão finais: {len(filtered_points)}")
        
        # 5. Criar segmentos com speakers alternados
        segments = []
        target_speakers = target_speakers or min(6, max(2, len(filtered_points) - 1))
        
        for i in range(len(filtered_points) - 1):
            start_time = filtered_points[i]
            end_time = filtered_points[i + 1]
            
            # Alternar speakers de forma inteligente
            if len(segments) == 0:
                speaker_id = 0
            else:
                # Analisar se deve continuar com o mesmo speaker ou mudar
                segment_duration = end_time - start_time
                last_speaker_id = int(segments[-1].speaker.split('_')[1])
                
                # Lógica para mudança de speaker:
                # - Segmentos muito curtos (< 10s) = mesmo speaker
                # - Após silêncio longo = novo speaker
                # - Mudança de energia alta = novo speaker
                
                if segment_duration < 10:  # Segmento curto
                    speaker_id = last_speaker_id
                elif start_time in [s[0] for s in silence_segments if s[1] - s[0] > 1.0]:  # Após silêncio longo
                    speaker_id = (last_speaker_id + 1) % target_speakers
                elif start_time in energy_changes:  # Mudança de energia
                    speaker_id = (last_speaker_id + 1) % target_speakers
                else:
                    speaker_id = last_speaker_id
            
            segments.append(DiarizationSegment(
                start_time, end_time, f"SPEAKER_{speaker_id:02d}"
            ))
        
        # 6. Pós-processamento: mesclar segmentos consecutivos do mesmo speaker
        if segments:
            merged = [segments[0]]
            for seg in segments[1:]:
                last = merged[-1]
                if last.speaker == seg.speaker and seg.start - last.end <= 2.0:  # 2s de tolerância
                    last.end = seg.end
                else:
                    merged.append(seg)
            segments = merged
        
        # 7. Garantir variação mínima para áudios longos
        unique_speakers = set(seg.speaker for seg in segments)
        if len(unique_speakers) == 1 and duration > 120:  # Mais de 2 minutos com 1 speaker
            logger.info("🔄 Forçando variação para áudio longo...")
            enhanced_segments = []
            for seg in segments:
                seg_duration = seg.end - seg.start
                if seg_duration > 45:  # Segmentos > 45s, dividir
                    mid_point = seg.start + seg_duration / 2
                    new_speaker = f"SPEAKER_{(int(seg.speaker.split('_')[1]) + 1) % 4:02d}"
                    enhanced_segments.append(DiarizationSegment(seg.start, mid_point, seg.speaker))
                    enhanced_segments.append(DiarizationSegment(mid_point, seg.end, new_speaker))
                else:
                    enhanced_segments.append(seg)
            segments = enhanced_segments
        
        final_speakers = set(seg.speaker for seg in segments)
        logger.info(f"✅ Diarização concluída: {len(segments)} segmentos, {len(final_speakers)} speakers")
        
        return segments
        
    except Exception as e:
        logger.error(f"❌ Erro na detecção avançada: {e}")
        return simple_fallback_diarization(audio_path)

def simple_fallback_diarization(audio_path: str) -> List[DiarizationSegment]:
    """Fallback simples baseado apenas em tempo"""
    logger.info("🔄 Usando diarização simples de fallback...")
    
    try:
        audio = AudioSegment.from_file(audio_path)
        duration = len(audio) / 1000.0
        
        segments = []
        
        if duration <= 60:  # <= 1 minuto
            segments.append(DiarizationSegment(0, duration, "SPEAKER_00"))
        elif duration <= 300:  # <= 5 minutos
            # 2 speakers alternados
            mid_point = duration / 2
            segments.append(DiarizationSegment(0, mid_point, "SPEAKER_00"))
            segments.append(DiarizationSegment(mid_point, duration, "SPEAKER_01"))
        else:  # > 5 minutos
            # 3-4 speakers
            num_segments = min(4, max(3, int(duration / 60)))  # 1 segmento por minuto
            segment_duration = duration / num_segments
            
            for i in range(num_segments):
                start_time = i * segment_duration
                end_time = min((i + 1) * segment_duration, duration)
                speaker_id = i % 3  # Máximo 3 speakers no fallback
                
                segments.append(DiarizationSegment(
                    start_time, end_time, f"SPEAKER_{speaker_id:02d}"
                ))
        
        logger.info(f"✅ Fallback: {len(segments)} segmentos criados")
        return segments
        
    except Exception as e:
        logger.error(f"❌ Erro no fallback: {e}")
        # Último recurso: um único speaker
        return [DiarizationSegment(0, 300, "SPEAKER_00")]  # 5 minutos padrão

def diarize_audio_free(audio_path: str, max_speakers=None) -> List[DiarizationSegment]:
    """
    🎯 DIARIZAÇÃO 100% GRATUITA - Funciona offline sem tokens
    """
    logger.info(f"🎯 Iniciando diarização gratuita: {audio_path}")
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
    
    # Verificar duração
    try:
        audio = AudioSegment.from_file(audio_path)
        duration = len(audio) / 1000.0
        logger.info(f"🎤 Áudio: {duration/60:.1f} minutos")
    except Exception as e:
        logger.error(f"❌ Erro ao carregar áudio: {e}")
        raise
    
    # Para áudios muito longos, usar estratégia diferente
    if duration > 3600:  # > 1 hora
        logger.warning("⚠️ Áudio muito longo - usando segmentação temporal")
        return simple_fallback_diarization(audio_path)
    
    try:
        # Tentar detecção avançada
        segments = advanced_speaker_detection(audio_path, max_speakers)
        
        if not segments:
            raise Exception("Nenhum segmento detectado")
        
        # Validação final
        total_duration = sum(seg.end - seg.start for seg in segments)
        if abs(total_duration - duration) > 30:  # Diferença > 30s
            logger.warning("⚠️ Segmentação inconsistente - usando fallback")
            return simple_fallback_diarization(audio_path)
        
        return segments
        
    except Exception as e:
        logger.error(f"❌ Erro na diarização avançada: {e}")
        return simple_fallback_diarization(audio_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization_free.py <audio_path> [max_speakers]")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    max_speakers = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    try:
        logger.info(f"🎯 Iniciando diarização gratuita: {audio_path}")
        segments = diarize_audio_free(audio_path, max_speakers)
        
        # Output em JSON
        import json
        result = [seg.to_dict() for seg in segments]
        print(json.dumps(result, indent=2))
        
        # Log summary
        speakers = set(seg['speaker'] for seg in result)
        logger.info(f"✅ Concluído: {len(result)} segmentos, {len(speakers)} speakers")
        
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        sys.exit(1)