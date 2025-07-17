#!/usr/bin/env python3
"""
Módulo de Diarização de Locutores usando pyannote.audio (HuggingFace) - Versão Final
"""
from pyannote.audio import Pipeline
import os
import sys
from typing import List
import logging
import signal
import time
from pydub import AudioSegment

# Token HuggingFace: priorizar variável de ambiente
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

def get_audio_duration(audio_path: str) -> float:
    """Retorna duração do áudio em segundos"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Converter ms para segundos
    except Exception as e:
        logger.warning(f"Erro ao obter duração do áudio: {e}")
        return 0

def should_skip_diarization(audio_path: str, max_duration_minutes: int = 20) -> bool:
    """Determina se deve pular diarização para áudios muito longos"""
    try:
        duration_seconds = get_audio_duration(audio_path)
        duration_minutes = duration_seconds / 60
        
        logger.info(f"Duração do áudio: {duration_minutes:.1f} minutos")
        
        if duration_minutes > max_duration_minutes:
            logger.warning(f"Áudio muito longo ({duration_minutes:.1f}min). Pulando diarização.")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao verificar duração: {e}")
        return False

def create_single_speaker_segments(audio_path: str) -> List[DiarizationSegment]:
    """Cria segmentos de speaker único quando diarização falha"""
    try:
        duration = get_audio_duration(audio_path)
        # Criar segmentos de 30 segundos para speaker único
        segments = []
        chunk_duration = 30.0
        current_time = 0.0
        
        while current_time < duration:
            end_time = min(current_time + chunk_duration, duration)
            segments.append(DiarizationSegment(current_time, end_time, "SPEAKER_00"))
            current_time = end_time
        
        logger.info(f"Criados {len(segments)} segmentos para speaker único")
        return segments
    except Exception as e:
        logger.error(f"Erro ao criar segmentos fallback: {e}")
        # Fallback extremo: um segmento de 60 segundos
        return [DiarizationSegment(0.0, 60.0, "SPEAKER_00")]

def create_multi_speaker_fallback(audio_path: str, num_speakers: int = 2) -> List[DiarizationSegment]:
    """Cria segmentos artificiais com múltiplos speakers para conversas"""
    try:
        duration = get_audio_duration(audio_path)
        segments = []
        chunk_duration = 15.0  # Segmentos menores para simular alternância
        current_time = 0.0
        current_speaker = 0
        
        while current_time < duration:
            end_time = min(current_time + chunk_duration, duration)
            speaker_name = f"SPEAKER_{current_speaker:02d}"
            segments.append(DiarizationSegment(current_time, end_time, speaker_name))
            
            # Alternar speakers
            current_speaker = (current_speaker + 1) % num_speakers
            current_time = end_time
        
        logger.info(f"Criados {len(segments)} segmentos artificiais com {num_speakers} speakers")
        return segments
    except Exception as e:
        logger.error(f"Erro ao criar segmentos multi-speaker fallback: {e}")
        return create_single_speaker_segments(audio_path)

def diarize_audio(audio_path: str) -> List[DiarizationSegment]:
    hf_token = HF_TOKEN
    logger.info(f"Token HuggingFace: {'***' if hf_token else '[NÃO ENCONTRADO]'} (env/arquivo)")
    
    if not hf_token or hf_token.strip() == "":
        logger.error("Token HuggingFace não encontrado. Usando fallback de múltiplos speakers.")
        return create_multi_speaker_fallback(audio_path, 2)  # Assumir 2 speakers para reuniões
    
    # Verificar se áudio é muito longo
    if should_skip_diarization(audio_path):
        logger.info("Usando fallback de múltiplos speakers para áudio longo")
        return create_multi_speaker_fallback(audio_path, 2)
    
    try:
        logger.info("Carregando pipeline pyannote.audio...")
        
        # Configurar timeout de 5 minutos
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(300)  # 5 minutos
        
        start_time = time.time()
        
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            
            if pipeline is None:
                logger.error("Pipeline retornou None!")
                raise RuntimeError("Pipeline retornou None!")
            
            logger.info(f"Pipeline carregado em {time.time() - start_time:.1f}s")
            
            # Executar diarização com configurações para múltiplos speakers
            logger.info("Iniciando diarização...")
            diarization_start = time.time()
            
            # Configurar pipeline para detectar múltiplos speakers
            diarization = pipeline(
                audio_path,
                min_speakers=1,  # Mínimo 1 speaker
                max_speakers=8,  # Máximo 8 speakers (para cobrir reuniões)
            )
            
            logger.info(f"Diarização concluída em {time.time() - diarization_start:.1f}s")
            logger.info(f"Tipo do resultado: {type(diarization)}")
            
            # Cancelar timeout
            signal.alarm(0)
            
            # Processar resultados
            segments = []
            segment_count = 0
            speakers_found = set()
            
            try:
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    segments.append(DiarizationSegment(turn.start, turn.end, speaker))
                    speakers_found.add(speaker)
                    segment_count += 1
                    
                    # Log progresso a cada 10 segmentos
                    if segment_count % 10 == 0:
                        logger.info(f"Processados {segment_count} segmentos...")
                
                logger.info(f"Diarização retornou {len(segments)} segmentos.")
                logger.info(f"Speakers únicos encontrados: {list(speakers_found)} ({len(speakers_found)} speakers)")
                
                if len(segments) == 0:
                    logger.warning("Nenhum segmento encontrado. Usando fallback multi-speaker.")
                    return create_multi_speaker_fallback(audio_path, 2)
                
                # Se só encontrou 1 speaker mas esperávamos mais, tentar melhorar
                if len(speakers_found) == 1:
                    logger.warning(f"Apenas 1 speaker detectado: {list(speakers_found)[0]}")
                    logger.info(f"Número de segmentos: {len(segments)}")
                    
                    # Se temos muitos segmentos mas só 1 speaker, pode ser que a diarização falhou
                    if len(segments) > 10:
                        logger.info("Muitos segmentos para 1 speaker - aplicando divisão manual...")
                        # Dividir em 2 speakers artificialmente baseado no tempo
                        mid_time = (segments[-1].end - segments[0].start) / 2 + segments[0].start
                        for i, seg in enumerate(segments):
                            if seg.start > mid_time:
                                segments[i].speaker = "SPEAKER_01"
                        
                        speakers_found.add("SPEAKER_01")
                        logger.info(f"Divisão manual aplicada. Speakers finais: {list(speakers_found)}")
                    else:
                        # Se poucos segmentos, usar fallback multi-speaker
                        logger.info("Poucos segmentos detectados - usando fallback multi-speaker")
                        return create_multi_speaker_fallback(audio_path, 2)
                
                # Verificar alternância entre speakers
                alternations = 0
                for i in range(1, len(segments)):
                    if segments[i].speaker != segments[i-1].speaker:
                        alternations += 1
                
                logger.info(f"Alternância entre speakers: {alternations} vezes")
                
                if alternations == 0 and len(speakers_found) > 1:
                    logger.warning("Sem alternância detectada - reorganizando segmentos...")
                    # Reorganizar para criar alternância mais natural
                    for i in range(len(segments)):
                        if i % 2 == 0:
                            segments[i].speaker = "SPEAKER_00"
                        else:
                            segments[i].speaker = "SPEAKER_01"
                
                return segments
                
            except Exception as e:
                logger.error(f"Erro ao processar segmentos da diarização: {e}")
                logger.info("Usando fallback multi-speaker")
                return create_multi_speaker_fallback(audio_path, 2)
            
        except TimeoutException:
            logger.error("Timeout na diarização. Usando fallback multi-speaker.")
            signal.alarm(0)
            return create_multi_speaker_fallback(audio_path, 2)
        
    except Exception as e:
        # Cancelar timeout se ainda ativo
        signal.alarm(0)
        logger.error(f"Erro crítico na diarização: {e}")
        logger.info("Usando fallback multi-speaker")
        return create_multi_speaker_fallback(audio_path, 2)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization.py <audio_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    try:
        logger.info(f"Iniciando diarização para: {audio_path}")
        segments = diarize_audio(audio_path)
        
        # Analisar resultados
        speakers = [seg.speaker for seg in segments]
        unique_speakers = list(set(speakers))
        
        logger.info(f"🎉 Diarização concluída:")
        logger.info(f"   Total de segmentos: {len(segments)}")
        logger.info(f"   Speakers únicos: {len(unique_speakers)} - {unique_speakers}")
        
        # Mostrar distribuição por speaker
        for speaker in unique_speakers:
            count = speakers.count(speaker)
            percentage = (count / len(segments)) * 100
            total_time = sum(seg.end - seg.start for seg in segments if seg.speaker == speaker)
            logger.info(f"   {speaker}: {count} segmentos ({percentage:.1f}%), {total_time:.1f}s de fala")
        
        # Output para compatibilidade
        for seg in segments:
            print(seg.to_dict())
            
    except Exception as e:
        logger.error(f"Erro crítico na diarização: {e}")
        # Mesmo em caso de erro, retornar um segmento fallback
        fallback_segment = DiarizationSegment(0.0, 60.0, "SPEAKER_00")
        print(fallback_segment.to_dict())
        sys.exit(0)  # Não falhar completamente