#!/usr/bin/env python3
"""
Módulo de Diarização de Locutores usando pyannote.audio (HuggingFace)
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

def diarize_audio(audio_path: str) -> List[DiarizationSegment]:
    hf_token = HF_TOKEN
    logger.info(f"Token HuggingFace: {'***' if hf_token else '[NÃO ENCONTRADO]'} (env/arquivo)")
    
    if not hf_token or hf_token.strip() == "":
        logger.error("Token HuggingFace não encontrado. Usando fallback de speaker único.")
        return create_single_speaker_segments(audio_path)
    
    # Verificar se áudio é muito longo
    if should_skip_diarization(audio_path):
        logger.info("Usando fallback de speaker único para áudio longo")
        return create_single_speaker_segments(audio_path)
    
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
            
            # Executar diarização
            logger.info("Iniciando diarização...")
            diarization_start = time.time()
            
            diarization = pipeline(audio_path)
            
            logger.info(f"Diarização concluída em {time.time() - diarization_start:.1f}s")
            logger.info(f"Tipo do resultado: {type(diarization)}")
            
            # Cancelar timeout
            signal.alarm(0)
            
            # Processar resultados
            segments = []
            segment_count = 0
            
            try:
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    segments.append(DiarizationSegment(turn.start, turn.end, speaker))
                    segment_count += 1
                    
                    # Log progresso a cada 10 segmentos
                    if segment_count % 10 == 0:
                        logger.info(f"Processados {segment_count} segmentos...")
                
                logger.info(f"Diarização retornou {len(segments)} segmentos.")
                
                if len(segments) == 0:
                    logger.warning("Nenhum segmento encontrado. Usando fallback.")
                    return create_single_speaker_segments(audio_path)
                
                return segments
                
            except Exception as e:
                logger.error(f"Erro ao processar segmentos da diarização: {e}")
                logger.info("Usando fallback de speaker único")
                return create_single_speaker_segments(audio_path)
            
        except TimeoutException:
            logger.error("Timeout na diarização. Usando fallback de speaker único.")
            signal.alarm(0)
            return create_single_speaker_segments(audio_path)
        
    except Exception as e:
        # Cancelar timeout se ainda ativo
        signal.alarm(0)
        logger.error(f"Erro crítico na diarização: {e}")
        logger.info("Usando fallback de speaker único")
        return create_single_speaker_segments(audio_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization.py <audio_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    try:
        logger.info(f"Iniciando diarização para: {audio_path}")
        segments = diarize_audio(audio_path)
        
        logger.info(f"Diarização concluída com {len(segments)} segmentos")
        
        for seg in segments:
            print(seg.to_dict())
            
    except Exception as e:
        logger.error(f"Erro crítico na diarização: {e}")
        # Mesmo em caso de erro, retornar um segmento fallback
        fallback_segment = DiarizationSegment(0.0, 60.0, "SPEAKER_00")
        print(fallback_segment.to_dict())
        sys.exit(0)  # Não falhar completamente