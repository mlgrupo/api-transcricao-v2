#!/usr/bin/env python3
"""
Sistema de Transcrição Avançado com Diarização Real de Locutores (SpeechBrain + Whisper)
"""
import sys
import json
import logging
import whisper
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import re
from diarization import diarize_audio, DiarizationSegment

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np

# Processamento de texto
from text_processor import TextProcessor, TextProcessingRules

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioPreprocessor:
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
    def normalize_audio(self, audio: AudioSegment) -> AudioSegment:
        try:
            return normalize(audio)
        except Exception as e:
            logger.warning(f"Erro na normalização: {e}")
            return audio
    def convert_format(self, audio: AudioSegment) -> AudioSegment:
        try:
            if audio.frame_rate != self.sample_rate:
                audio = audio.set_frame_rate(self.sample_rate)
            if audio.channels != self.channels:
                audio = audio.set_channels(self.channels)
            return audio
        except Exception as e:
            logger.warning(f"Erro na conversão de formato: {e}")
            return audio
    def process(self, audio: AudioSegment) -> AudioSegment:
        logger.info("Iniciando pré-processamento de áudio...")
        original_duration = len(audio)
        audio = self.normalize_audio(audio)
        audio = self.convert_format(audio)
        final_duration = len(audio)
        logger.info(f"Pré-processamento concluído: {original_duration}ms -> {final_duration}ms")
        return audio

class TextPostProcessor:
    def __init__(self):
        self.text_processor = TextProcessor(TextProcessingRules(
            capitalize_sentences=True,
            fix_spaces=True,
            ensure_final_punctuation=True,
            normalize_numbers=True,
            fix_common_errors=True,
            normalize_punctuation=True
        ))
    def clean_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        text = self.text_processor.process(text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        start_seconds = int(start_time)
        end_seconds = int(end_time)
        start_h = start_seconds // 3600
        start_m = (start_seconds % 3600) // 60
        start_s = start_seconds % 60
        end_h = end_seconds // 3600
        end_m = (end_seconds % 3600) // 60
        end_s = end_seconds % 60
        return f"[{start_h:02d}:{start_m:02d}:{start_s:02d} - {end_h:02d}:{end_m:02d}:{end_s:02d}]"

class TranscriptionProcessor:
    def __init__(self):
        self.audio_preprocessor = AudioPreprocessor()
        self.text_processor = TextPostProcessor()
        self.model = None
    def load_model(self, model_size: str = "turbo") -> whisper.Whisper:
        if self.model is None:
            logger.info(f"Carregando modelo Whisper: {model_size}")
            self.model = whisper.load_model(model_size)
            logger.info("Modelo carregado com sucesso")
        return self.model
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        logger.info(f"Iniciando transcrição avançada com diarização: {audio_path}")
        try:
            # Carregar áudio e pré-processar
            audio = AudioSegment.from_file(audio_path)
            audio = self.audio_preprocessor.process(audio)
            # Salvar áudio processado temporariamente
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                temp_path = temp_file.name
            # Diarização real
            logger.info("Rodando diarização com pyannote.audio...")
            diarization_segments: List[DiarizationSegment] = diarize_audio(temp_path)
            logger.info(f"{len(diarization_segments)} segmentos de locutores detectados.")
            # Carregar modelo Whisper
            model = self.load_model("large-v3")
            # Transcrever cada segmento
            formatted_segments = []
            for i, seg in enumerate(diarization_segments):
                # Extrair segmento do áudio
                seg_audio = audio[ int(seg.start*1000) : int(seg.end*1000) ]
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                    seg_audio.export(seg_file.name, format='wav')
                    seg_path = seg_file.name
                # Transcrever segmento
                result = model.transcribe(
                    seg_path,
                    language="pt",
                    task="transcribe",
                    verbose=False,
                    fp16=False,
                    temperature=0.0,
                    compression_ratio_threshold=2.4,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=True,
                    initial_prompt="Este é um áudio em português brasileiro."
                )
                os.unlink(seg_path)
                processed_text = self.text_processor.clean_text(result["text"])
                timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                formatted_segments.append(f"{timestamp}\n{seg.speaker}: {processed_text}")
            os.unlink(temp_path)
            return "\n\n".join(formatted_segments)
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            raise

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Por favor, forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
        processor = TranscriptionProcessor()
        result = processor.transcribe_audio(audio_path, output_dir)
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"Transcrição salva em: {output_file}")
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "diarization_whisper",
            "timestamp": datetime.now().isoformat()
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Erro na execução: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
