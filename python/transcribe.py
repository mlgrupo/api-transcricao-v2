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
import gc
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np

# NOVO: Função para dividir áudio longo em partes menores
def split_audio(input_path, chunk_length_ms=10*60*1000):  # 10 minutos por padrão
    audio = AudioSegment.from_file(input_path)
    chunks = []
    for i in range(0, len(audio), chunk_length_ms):
        chunk = audio[i:i+chunk_length_ms]
        chunk_path = f"{input_path}_chunk_{i//chunk_length_ms}.wav"
        try:
            chunk.export(chunk_path, format="wav")
            chunks.append(chunk_path)
        except Exception as e:
            logger.error(f"[ERRO] Falha ao exportar chunk {i+1}: {e}\n{traceback.format_exc()}")
            continue
    return chunks

# Processamento de texto
from text_processor import TextProcessor, TextProcessingRules

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)
logger.info('==== [BOOT] Script transcribe.py iniciado ===', extra={}, stacklevel=1)
logger.info(f'[BOOT] Diretório de trabalho atual: {os.getcwd()}', extra={}, stacklevel=1)
logger.info(f'[BOOT] Versão do Python: {sys.version}', extra={}, stacklevel=1)

# NOVO: Script auxiliar para transcrever um chunk isoladamente
CHUNK_WORKER_SCRIPT = "chunk_worker.py"

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
        logger.info("Iniciando pré-processamento de áudio...", extra={}, stacklevel=1)
        original_duration = len(audio)
        audio = self.normalize_audio(audio)
        audio = self.convert_format(audio)
        final_duration = len(audio)
        logger.info(f"Pré-processamento concluído: {original_duration}ms -> {final_duration}ms", extra={}, stacklevel=1)
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
            logger.info(f"carregando Whisper: {model_size}", extra={}, stacklevel=1)
            self.model = whisper.load_model(model_size)
            logger.info("Modelo carregado com sucesso", extra={}, stacklevel=1)
        return self.model
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        logger.info(f"[INÍCIO] Transcrição avançada com diarização: {audio_path}", extra={}, stacklevel=1)
        all_formatted_segments = []
        try:
            logger.info("[ETAPA] Carregando áudio original...", extra={}, stacklevel=1)
            audio = AudioSegment.from_file(audio_path)
            logger.info(f"[OK] Áudio carregado: {len(audio)/1000:.1f}s", extra={}, stacklevel=1)
            chunk_length_ms = 10*60*1000  # 10 minutos
            if len(audio) > chunk_length_ms:
                logger.info(f"[ETAPA] Áudio longo detectado ({len(audio)/60000:.1f} min). Dividindo em partes de 10 minutos...", extra={}, stacklevel=1)
                chunk_paths = split_audio(audio_path, chunk_length_ms)
                logger.info(f"[OK] Divisão concluída: {len(chunk_paths)} partes.", extra={}, stacklevel=1)
            else:
                chunk_paths = [audio_path]
                logger.info("[OK] Áudio curto, sem divisão.", extra={}, stacklevel=1)
            chunk_results_dir = output_dir or os.path.dirname(audio_path)
            os.makedirs(chunk_results_dir, exist_ok=True)
            chunk_txt_files = []
            max_workers = 4  # Metade dos vCPUs para robustez
            def process_chunk(idx, chunk_path):
                logger.info(f'[BOOT] Iniciando processamento do chunk {idx+1}', extra={}, stacklevel=1)
                chunk_txt_path = os.path.join(chunk_results_dir, f"chunk_{idx+1}.txt")
                chunk_err_path = os.path.join(chunk_results_dir, f"chunk_{idx+1}.err")
                if os.path.exists(chunk_txt_path):
                    logger.info(f"[SKIP] Chunk {idx+1} já processado. Pulando...", extra={}, stacklevel=1)
                    return chunk_txt_path
                logger.info(f"[ETAPA] Processando chunk {idx+1}/{len(chunk_paths)} em subprocesso: {chunk_path}", extra={}, stacklevel=1)
                try:
                    result = subprocess.run([
                        sys.executable, CHUNK_WORKER_SCRIPT, chunk_path, chunk_txt_path, chunk_err_path
                    ], capture_output=True, text=True, timeout=None)
                    if result.returncode == 0 and os.path.exists(chunk_txt_path):
                        logger.info(f"[OK] Chunk {idx+1} processado e salvo em {chunk_txt_path}", extra={}, stacklevel=1)
                        return chunk_txt_path
                    else:
                        logger.error(f"[ERRO] Subprocesso do chunk {idx+1} falhou. Veja {chunk_err_path}. STDERR: {result.stderr}", extra={}, stacklevel=1)
                        with open(chunk_err_path, 'a', encoding='utf-8') as errf:
                            errf.write(f"\n[STDERR]\n{result.stderr}")
                        return None
                except Exception as e:
                    logger.error(f"[ERRO] Falha inesperada ao processar chunk {idx+1} em subprocesso: {e}\n{traceback.format_exc()}", extra={}, stacklevel=1)
                    with open(chunk_err_path, 'w', encoding='utf-8') as errf:
                        errf.write(f"[ERRO] Falha inesperada ao processar chunk {idx+1} em subprocesso: {e}\n{traceback.format_exc()}")
                    return None
                finally:
                    gc.collect()
                    try:
                        if chunk_path != audio_path and os.path.exists(chunk_path):
                            os.remove(chunk_path)
                            logger.info(f"[OK] Chunk temporário removido: {chunk_path}", extra={}, stacklevel=1)
                    except Exception as e:
                        logger.warning(f"[WARN] Falha ao remover chunk temporário: {e}", extra={}, stacklevel=1)
                logger.info(f'[BOOT] Fim do processamento do chunk {idx+1}', extra={}, stacklevel=1)
            # Paralelismo controlado
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {executor.submit(process_chunk, idx, chunk_path): idx for idx, chunk_path in enumerate(chunk_paths)}
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        txt_path = future.result()
                        if txt_path:
                            chunk_txt_files.append(txt_path)
                    except Exception as e:
                        logger.error(f"[ERRO] Falha inesperada no futuro do chunk {idx+1}: {e}\n{traceback.format_exc()}", extra={}, stacklevel=1)
            # Unir todos os resultados dos chunks na ordem correta
            final_result = []
            for idx in range(len(chunk_paths)):
                txt_path = os.path.join(chunk_results_dir, f"chunk_{idx+1}.txt")
                if os.path.exists(txt_path):
                    try:
                        with open(txt_path, 'r', encoding='utf-8') as inf:
                            final_result.append(inf.read())
                    except Exception as e:
                        logger.error(f"[ERRO] Falha ao ler resultado do chunk: {txt_path}: {e}", extra={}, stacklevel=1)
            logger.info("[FIM] Transcrição concluída com sucesso.", extra={}, stacklevel=1)
            return "\n\n".join(final_result)
        except Exception as e:
            logger.error(f"[ERRO FATAL] Erro na transcrição: {e}\n{traceback.format_exc()}", extra={}, stacklevel=1)
            return f"[ERRO FATAL] Erro na transcrição: {e}"  # Nunca lança, sempre retorna string explicando o erro

def main():
    logger.info('[BOOT] Entrou no main() do transcribe.py', extra={}, stacklevel=1)
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Por favor, forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False), flush=True)
        sys.exit(1)
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    logger.info(f'[BOOT] Argumento recebido para áudio: {audio_path}', extra={}, stacklevel=1)
    logger.info(f'[BOOT] Argumento recebido para output_dir: {output_dir}', extra={}, stacklevel=1)
    try:
        if not os.path.exists(audio_path):
            logger.error(f'[BOOT] Arquivo de áudio não encontrado: {audio_path}', extra={}, stacklevel=1)
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
        processor = TranscriptionProcessor()
        logger.info('[BOOT] Instanciou TranscriptionProcessor', extra={}, stacklevel=1)
        result = processor.transcribe_audio(audio_path, output_dir)
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"Transcrição salva em: {output_file}", extra={}, stacklevel=1)
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "diarization_whisper",
            "timestamp": datetime.now().isoformat()
        }
        print(json.dumps(output, ensure_ascii=False), flush=True)
    except Exception as e:
        logger.error(f"Erro na execução: {e}", extra={}, stacklevel=1)
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

# NOVO: Script worker para processar um chunk isoladamente
if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[0].endswith("chunk_worker.py"):
    # Este bloco só roda se chamado como subprocesso worker
    chunk_path = sys.argv[1]
    chunk_txt_path = sys.argv[2]
    chunk_err_path = sys.argv[3]
    try:
        processor = TranscriptionProcessor()
        model = processor.load_model("medium")
        chunk_audio = AudioSegment.from_file(chunk_path)
        chunk_audio = processor.audio_preprocessor.process(chunk_audio)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            chunk_audio.export(temp_file.name, format='wav')
            temp_path = temp_file.name
        try:
            diarization_segments: List[DiarizationSegment] = diarize_audio(temp_path)
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
                processed_text = processor.text_processor.clean_text(result["text"])
                timestamp = processor.text_processor.format_timestamp(seg.start, seg.end)
                formatted_segments.append(f"{timestamp}\n{seg.speaker}: {processed_text}")
            chunk_text = "\n\n".join(formatted_segments)
            with open(chunk_txt_path, 'w', encoding='utf-8') as outf:
                outf.write(chunk_text)
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
                processed_text = processor.text_processor.clean_text(result["text"])
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
        with open(chunk_err_path, 'a', encoding='utf-8') as errf:
            errf.write(f"[ERRO FATAL] Falha inesperada no worker: {e}\n{traceback.format_exc()}")
        sys.exit(1)
