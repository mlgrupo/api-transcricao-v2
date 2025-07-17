#!/usr/bin/env python3
import sys
import os
import tempfile
import traceback
import gc
from pydub import AudioSegment
from diarization import diarize_audio, DiarizationSegment
from text_processor import TextProcessor, TextProcessingRules
import whisper
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)
# FileHandler para log em arquivo
try:
    log_path = os.path.join(os.path.dirname(__file__), "chunk_worker.log")
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    file_handler.flush = lambda: None  # Garantir compatibilidade
    logging.getLogger().addHandler(file_handler)
    logger.info(f'[BOOT] FileHandler de log inicializado em {log_path}', extra={}, stacklevel=1)
except Exception as e:
    print(f'[ERRO] Falha ao inicializar FileHandler de log: {e}', flush=True)
logger.info('==== [BOOT] Script chunk_worker.py iniciado ===', extra={}, stacklevel=1)
logger.info(f'[BOOT] Diretório de trabalho atual: {os.getcwd()}', extra={}, stacklevel=1)
logger.info(f'[BOOT] Versão do Python: {sys.version}', extra={}, stacklevel=1)

if __name__ == "__main__" and len(sys.argv) == 4:
    logger.info(f'[BOOT] Argumentos recebidos: chunk_path={sys.argv[1]}, chunk_txt_path={sys.argv[2]}, chunk_err_path={sys.argv[3]}', extra={}, stacklevel=1)
    chunk_path = sys.argv[1]
    chunk_txt_path = sys.argv[2]
    chunk_err_path = sys.argv[3]
    try:
        logger.info('[BOOT] Iniciando processamento do chunk', extra={}, stacklevel=1)
        class AudioPreprocessor:
            def __init__(self):
                self.sample_rate = 16000
                self.channels = 1
            def normalize_audio(self, audio: AudioSegment) -> AudioSegment:
                try:
                    from pydub.effects import normalize
                    return normalize(audio)
                except Exception as e:
                    return audio
            def convert_format(self, audio: AudioSegment) -> AudioSegment:
                try:
                    if audio.frame_rate != self.sample_rate:
                        audio = audio.set_frame_rate(self.sample_rate)
                    if audio.channels != self.channels:
                        audio = audio.set_channels(self.channels)
                    return audio
                except Exception as e:
                    return audio
            def process(self, audio: AudioSegment) -> AudioSegment:
                audio = self.normalize_audio(audio)
                audio = self.convert_format(audio)
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
                import re
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
        audio_preprocessor = AudioPreprocessor()
        text_processor = TextPostProcessor()
        model = whisper.load_model("medium")
        chunk_audio = AudioSegment.from_file(chunk_path)
        chunk_audio = audio_preprocessor.process(chunk_audio)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            chunk_audio.export(temp_file.name, format='wav')
            temp_path = temp_file.name
        try:
            diarization_segments = diarize_audio(temp_path)
            formatted_segments = []
            for i, seg in enumerate(diarization_segments):
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
                except Exception as e:
                    with open(chunk_err_path, 'a', encoding='utf-8') as errf:
                        errf.write(f"[ERRO] Falha ao transcrever segmento: {e}\n{traceback.format_exc()}")
                    continue
                finally:
                    if os.path.exists(seg_path):
                        os.unlink(seg_path)
                processed_text = text_processor.clean_text(result["text"])
                timestamp = text_processor.format_timestamp(seg.start, seg.end)
                formatted_segments.append(f"{timestamp}\n{seg.speaker}: {processed_text}")
            chunk_text = "\n\n".join(formatted_segments)
            with open(chunk_txt_path, 'w', encoding='utf-8') as outf:
                outf.write(chunk_text)
            logger.info('[BOOT] Processamento do chunk finalizado com sucesso', extra={}, stacklevel=1)
        except Exception as diarization_error:
            with open(chunk_err_path, 'a', encoding='utf-8') as errf:
                errf.write(f"[ERRO] Falha na diarização: {diarization_error}\n{traceback.format_exc()}")
            # Fallback: transcrever chunk inteiro sem diarização
            try:
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
                processed_text = text_processor.clean_text(result["text"])
                with open(chunk_txt_path, 'w', encoding='utf-8') as outf:
                    outf.write(f"[Sem diarização]: {processed_text}")
            except Exception as fallback_error:
                with open(chunk_err_path, 'a', encoding='utf-8') as errf:
                    errf.write(f"[ERRO] Falha total ao transcrever chunk: {fallback_error}\n{traceback.format_exc()}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        gc.collect()
        sys.exit(0)
    except Exception as e:
        logger.error(f"[ERRO FATAL] Falha inesperada no worker: {e}\n{traceback.format_exc()}", extra={}, stacklevel=1)
        sys.exit(1) 