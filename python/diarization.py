#!/usr/bin/env python3
"""
Módulo de Diarização de Locutores usando pyannote.audio (HuggingFace)
"""
from pyannote.audio import Pipeline
import os
import sys
from typing import List
import logging

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

def diarize_audio(audio_path: str) -> List[DiarizationSegment]:
    hf_token = HF_TOKEN
    logger.info(f"Token HuggingFace: {'***' if hf_token else '[NÃO ENCONTRADO]'} (env/arquivo)")
    if not hf_token or hf_token.strip() == "":
        logger.error("Token HuggingFace não encontrado. Defina a variável de ambiente HF_TOKEN.")
        raise RuntimeError("Token HuggingFace não encontrado. Defina a variável de ambiente HF_TOKEN.")
    try:
        logger.info("Carregando pipeline pyannote.audio...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        if pipeline is None:
            logger.error("Pipeline pyannote.audio retornou None! Verifique o token e dependências.")
            raise RuntimeError("Pipeline pyannote.audio retornou None! Verifique o token e dependências.")
        logger.info("Pipeline carregado com sucesso.")
        # Chamada sem min_duration_on/min_duration_off
        diarization = pipeline(
            audio_path,
            min_speakers=1,
            max_speakers=2
        )
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(DiarizationSegment(turn.start, turn.end, speaker))
        logger.info(f"Diarização retornou {len(segments)} segmentos.")
        return segments
    except Exception as e:
        logger.error(f"Erro ao carregar pipeline ou rodar diarização: {e}")
        raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization.py <audio_path>")
        sys.exit(1)
    audio_path = sys.argv[1]
    try:
        segments = diarize_audio(audio_path)
        for seg in segments:
            print(seg.to_dict())
    except Exception as e:
        print(f"Erro crítico na diarização: {e}")
        sys.exit(2) 