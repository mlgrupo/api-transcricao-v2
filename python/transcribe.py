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
import traceback

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np

# NOVO: Função para dividir áudio longo em partes menores
def split_audio(input_path, chunk_length_ms=30*60*1000):  # 30 minutos
    audio = AudioSegment.from_file(input_path)
    chunks = []
    for i in range(0, len(audio), chunk_length_ms):
        chunk = audio[i:i+chunk_length_ms]
        chunk_path = f"{input_path}_chunk_{i//chunk_length_ms}.wav"
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)
    return chunks

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
    def load_model(self, model_size: str = "medium") -> whisper.Whisper:
        if self.model is None:
            logger.info(f"carregando Whisper: {model_size}")
            self.model = whisper.load_model(model_size)
            logger.info("Modelo carregado com sucesso")
        return self.model
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        logger.info(f"[INÍCIO] Transcrição avançada com diarização: {audio_path}")
        try:
            logger.info("[ETAPA] Carregando áudio original...")
            audio = AudioSegment.from_file(audio_path)
            logger.info(f"[OK] Áudio carregado: {len(audio)/1000:.1f}s")
            chunk_length_ms = 10*60*1000  # 10 minutos
            if len(audio) > chunk_length_ms:
                logger.info(f"[ETAPA] Áudio longo detectado ({len(audio)/60000:.1f} min). Dividindo em partes de 10 minutos...")
                chunk_paths = split_audio(audio_path, chunk_length_ms)
                logger.info(f"[OK] Divisão concluída: {len(chunk_paths)} partes.")
            else:
                chunk_paths = [audio_path]
                logger.info("[OK] Áudio curto, sem divisão.")
            all_formatted_segments = []
            model = self.load_model("medium")  # Sempre usar 'medium'
            for idx, chunk_path in enumerate(chunk_paths):
                logger.info(f"[ETAPA] Processando chunk {idx+1}/{len(chunk_paths)}: {chunk_path}")
                try:
                    logger.info("[ETAPA] Carregando chunk de áudio...")
                    chunk_audio = AudioSegment.from_file(chunk_path)
                    logger.info("[OK] Chunk carregado.")
                    logger.info("[ETAPA] Pré-processando chunk...")
                    chunk_audio = self.audio_preprocessor.process(chunk_audio)
                    logger.info("[OK] Pré-processamento concluído.")
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                        chunk_audio.export(temp_file.name, format='wav')
                        temp_path = temp_file.name
                    try:
                        logger.info(f"[ETAPA] Rodando diarização com pyannote.audio no chunk {idx+1}...")
                        diarization_segments: List[DiarizationSegment] = diarize_audio(temp_path)
                        logger.info(f"[OK] {len(diarization_segments)} segmentos de locutores detectados.")
                        formatted_segments = []
                        for i, seg in enumerate(diarization_segments):
                            logger.info(f"[ETAPA] Transcrevendo segmento {i+1}/{len(diarization_segments)} do chunk {idx+1}...")
                            seg_audio = chunk_audio[ int(seg.start*1000) : int(seg.end*1000) ]
                            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                                seg_audio.export(seg_file.name, format='wav')
                                seg_path = seg_file.name
                            try:
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
                                logger.info(f"[OK] Segmento {i+1} transcrito.")
                            except Exception as e:
                                logger.error(f"[ERRO] Falha ao transcrever segmento {i+1}: {e}\n{traceback.format_exc()}")
                                formatted_segments.append(f"[ERRO] Falha ao transcrever segmento {i+1} do chunk {idx+1}: {e}")
                                continue
                            finally:
                                os.unlink(seg_path)
                            processed_text = self.text_processor.clean_text(result["text"])
                            timestamp = self.text_processor.format_timestamp(seg.start + idx*chunk_length_ms/1000, seg.end + idx*chunk_length_ms/1000)
                            formatted_segments.append(f"{timestamp}\n{seg.speaker}: {processed_text}")
                        all_formatted_segments.extend(formatted_segments)
                        logger.info(f"[OK] Chunk {idx+1} processado com sucesso (diarização).")
                    except Exception as diarization_error:
                        logger.error(f"[ERRO] Falha na diarização do chunk {idx+1}: {diarization_error}\n{traceback.format_exc()}")
                        # Fallback: transcrever o chunk inteiro sem diarização
                        try:
                            logger.info(f"[FALLBACK] Transcrevendo chunk {idx+1} inteiro sem diarização...")
                            result = model.transcribe(
                                temp_path,
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
                            processed_text = self.text_processor.clean_text(result["text"])
                            timestamp = self.text_processor.format_timestamp(0 + idx*chunk_length_ms/1000, len(chunk_audio)/1000 + idx*chunk_length_ms/1000)
                            all_formatted_segments.append(f"{timestamp}\n[Sem diarização]: {processed_text}")
                            logger.info(f"[OK] Chunk {idx+1} processado com sucesso (fallback sem diarização).")
                        except Exception as fallback_error:
                            logger.error(f"[ERRO] Falha total ao transcrever chunk {idx+1}: {fallback_error}\n{traceback.format_exc()}")
                            all_formatted_segments.append(f"[ERRO] Falha total ao transcrever chunk {idx+1}: {fallback_error}")
                    finally:
                        os.unlink(temp_path)
                    if chunk_path != audio_path:
                        try:
                            os.remove(chunk_path)
                            logger.info(f"[OK] Chunk temporário removido: {chunk_path}")
                        except Exception as e:
                            logger.warning(f"[WARN] Falha ao remover chunk temporário: {e}")
                except Exception as e:
                    logger.error(f"[ERRO] Falha inesperada ao processar chunk {idx+1}: {e}\n{traceback.format_exc()}")
                    all_formatted_segments.append(f"[ERRO] Falha inesperada ao processar chunk {idx+1}: {e}")
                    continue
            logger.info("[FIM] Transcrição concluída com sucesso.")
            return "\n\n".join(all_formatted_segments)
        except Exception as e:
            logger.error(f"[ERRO FATAL] Erro na transcrição: {e}\n{traceback.format_exc()}")
            return f"[ERRO FATAL] Erro na transcrição: {e}"  # Nunca lança, sempre retorna string explicando o erro

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
