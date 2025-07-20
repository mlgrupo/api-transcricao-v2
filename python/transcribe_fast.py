#!/usr/bin/env python3
"""
Sistema de Transcrição Ultra-Rápido (Whisper Tiny + Sem Diarização)
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

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioPreprocessor:
    def __init__(self):
        self.sample_rate = 1600     self.channels = 1    
    def speed_up_audio(self, audio: AudioSegment, speed_factor: float = 2.0 -> AudioSegment:
        elera o áudio para reduzir tempo de processamento"""
        try:
            accelerated_audio = audio._spawn(audio.raw_data, overrides={
               frame_rate: int(audio.frame_rate * speed_factor)
            })
            accelerated_audio = accelerated_audio.set_frame_rate(audio.frame_rate)
            logger.info(f"Áudio acelerado:[object Object]len(audio)}ms -> {len(accelerated_audio)}ms (speed: {speed_factor}x)")
            return accelerated_audio
        except Exception as e:
            logger.warning(f"Erro ao acelerar áudio: {e}")
            return audio
        
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
            logger.warning(fErro na conversão de formato: {e}")
            return audio
            
    def process(self, audio: AudioSegment, speed_up: bool = True) -> AudioSegment:
        logger.info("Iniciando pré-processamento de áudio...")
        original_duration = len(audio)
        
        if speed_up:
            audio = self.speed_up_audio(audio, 20lerar 2x
        
        audio = self.normalize_audio(audio)
        audio = self.convert_format(audio)
        final_duration = len(audio)
        logger.info(fPré-processamento concluído: [object Object]original_duration}ms -> {final_duration}ms")
        return audio

class FastTranscriptionProcessor:
    def __init__(self):
        self.audio_preprocessor = AudioPreprocessor()
        self.model = None
        
    def load_model(self) -> whisper.Whisper:
        if self.model is None:
            logger.info(Carregando modelo Whisper: tiny")
            self.model = whisper.load_model("tiny", device=cpu            logger.info("Modelo tiny carregado com sucesso")
        return self.model
        
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        logger.info(f"Iniciando transcrição ultra-rápida: {audio_path}")
        try:
            # Carregar e pré-processar áudio
            audio = AudioSegment.from_file(audio_path)
            audio = self.audio_preprocessor.process(audio, speed_up=True)
            
            # Salvar áudio processado temporariamente
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav)              temp_path = temp_file.name
                
            # Carregar modelo e transcrever
            model = self.load_model()
            logger.info("Iniciando transcrição com Whisper tiny...")
            
            result = model.transcribe(
                temp_path,
                language="pt,              task="transcribe,           verbose=False,
                fp16=False,
                temperature=0.0       compression_ratio_threshold=2.4               logprob_threshold=-1.0                no_speech_threshold=0.6         condition_on_previous_text=False,
                beam_size=1           initial_prompt=None,
                num_workers=1              best_of=1
            )
            
            os.unlink(temp_path)
            
            # Processar texto
            text = result["text"].strip()
            if not text:
                text =[Sem fala detectada]"
                
            logger.info(fTranscrição concluída: {len(text)} caracteres")
            return text
            
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            raise

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
          status": "error",
       error":Por favor, forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
        
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) >2else None
    
    try:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
        processor = FastTranscriptionProcessor()
        result = processor.transcribe_audio(audio_path, output_dir)
        
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, w, encoding='utf-8') as f:
                f.write(result)
            logger.info(fTranscrição salva em: {output_file}")
            
        output = {
            status": "success",
          textesult,
            languagept",
            processing_type:whisper_tiny_fast",
      timestamp:datetime.now().isoformat()
        }
        print(json.dumps(output, ensure_ascii=False))
        
    except Exception as e:
        logger.error(fErro na execução: {e}")
        print(json.dumps({
          status": "error",
          error": str(e)
        }, ensure_ascii=False))
        sys.exit(1if __name__ == "__main__":
    main() 