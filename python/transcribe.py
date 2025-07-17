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
import signal
import time
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

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Timeout no processamento")

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
        try:
            self.text_processor = TextProcessor(TextProcessingRules(
                capitalize_sentences=True,
                fix_spaces=True,
                ensure_final_punctuation=True,
                normalize_numbers=True,
                fix_common_errors=True,
                normalize_punctuation=True
            ))
        except Exception as e:
            logger.warning(f"Erro ao inicializar text_processor: {e}")
            self.text_processor = None
    
    def clean_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        
        try:
            if self.text_processor:
                text = self.text_processor.process(text)
        except Exception as e:
            logger.warning(f"Erro no processamento de texto: {e}")
        
        # Limpeza básica
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
    
    def load_model(self, model_size: str = "medium") -> whisper.Whisper:
        if self.model is None:
            logger.info(f"Carregando modelo Whisper: {model_size}")
            try:
                self.model = whisper.load_model(model_size)
                logger.info("Modelo carregado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao carregar modelo Whisper: {e}")
                # Tentar modelo menor
                logger.info("Tentando carregar modelo 'base'...")
                self.model = whisper.load_model("base")
                logger.info("Modelo 'base' carregado com sucesso")
        return self.model
    
    def transcribe_segment_safe(self, model, seg_path: str, retry_count: int = 2) -> str:
        """Transcreve um segmento com retry e fallback"""
        for attempt in range(retry_count + 1):
            try:
                # Configurar timeout de 2 minutos por segmento
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(120)  # 2 minutos
                
                result = model.transcribe(
                    seg_path,
                    language="pt",
                    task="transcribe",
                    verbose=False,
                    fp16=False,
                    temperature=0.0 if attempt == 0 else 0.2,  # Aumentar temperatura em retry
                    compression_ratio_threshold=2.4,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=attempt == 0,  # Desabilitar em retry
                    initial_prompt="Este é um áudio em português brasileiro. Transcreva com a maior precisão possível."
                )
                
                signal.alarm(0)  # Cancelar timeout
                return result["text"]
                
            except TimeoutException:
                signal.alarm(0)
                logger.warning(f"Timeout na transcrição do segmento (tentativa {attempt + 1})")
                if attempt < retry_count:
                    continue
                return "[Erro: timeout na transcrição]"
            except Exception as e:
                signal.alarm(0)
                logger.warning(f"Erro na transcrição do segmento (tentativa {attempt + 1}): {e}")
                if attempt < retry_count:
                    continue
                return "[Erro na transcrição do segmento]"
        
        return "[Erro: não foi possível transcrever este segmento]"
    
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        logger.info(f"Iniciando transcrição avançada com diarização: {audio_path}")
        temp_files = []
        
        try:
            # Verificar se arquivo existe
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Carregar áudio e pré-processar
            logger.info("Carregando e pré-processando áudio...")
            audio = AudioSegment.from_file(audio_path)
            audio = self.audio_preprocessor.process(audio)
            
            # Salvar áudio processado temporariamente
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                temp_path = temp_file.name
                temp_files.append(temp_path)
            
            # Diarização com fallback
            logger.info("Rodando diarização com pyannote.audio...")
            try:
                diarization_segments: List[DiarizationSegment] = diarize_audio(temp_path)
                logger.info(f"{len(diarization_segments)} segmentos de locutores detectados.")
            except Exception as e:
                logger.error(f"Erro na diarização: {e}")
                # Fallback: criar um segmento único
                audio_duration = len(audio) / 1000.0  # Converter para segundos
                diarization_segments = [DiarizationSegment(0.0, audio_duration, "SPEAKER_00")]
                logger.info("Usando segmento único como fallback")
            
            # Carregar modelo Whisper
            model = self.load_model("medium")
            
            # Transcrever cada segmento
            formatted_segments = []
            total_segments = len(diarization_segments)
            
            for i, seg in enumerate(diarization_segments):
                logger.info(f"Transcrevendo segmento {i+1}/{total_segments} ({seg.speaker})")
                
                try:
                    # Extrair segmento do áudio
                    start_ms = max(0, int(seg.start * 1000))
                    end_ms = min(len(audio), int(seg.end * 1000))
                    
                    if end_ms <= start_ms:
                        logger.warning(f"Segmento inválido: {start_ms}-{end_ms}ms")
                        continue
                    
                    seg_audio = audio[start_ms:end_ms]
                    
                    # Pular segmentos muito curtos (menos de 1 segundo)
                    if len(seg_audio) < 1000:
                        logger.info(f"Pulando segmento muito curto: {len(seg_audio)}ms")
                        continue
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                        seg_audio.export(seg_file.name, format='wav')
                        seg_path = seg_file.name
                        temp_files.append(seg_path)
                    
                    # Transcrever segmento
                    transcription_text = self.transcribe_segment_safe(model, seg_path, retry_count=1)
                    
                    # Processar texto
                    processed_text = self.text_processor.clean_text(transcription_text)
                    
                    if processed_text.strip():  # Só adicionar se tiver conteúdo
                        timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                        formatted_segments.append(f"{timestamp}\n{seg.speaker}: {processed_text}")
                
                except Exception as e:
                    logger.error(f"Erro ao processar segmento {i+1}: {e}")
                    # Continuar com próximo segmento
                    continue
            
            # Verificar se temos resultados
            if not formatted_segments:
                logger.warning("Nenhum segmento foi transcrito com sucesso")
                return "Não foi possível transcrever este áudio. Tente novamente ou verifique a qualidade do arquivo."
            
            result = "\n\n".join(formatted_segments)
            logger.info(f"Transcrição concluída com {len(formatted_segments)} segmentos")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            raise
        finally:
            # Limpar arquivos temporários
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Erro ao remover arquivo temporário {temp_file}: {e}")

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