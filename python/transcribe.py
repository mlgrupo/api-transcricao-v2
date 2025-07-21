#!/usr/bin/env python3
"""
Transcrição Simples e Eficiente
- Sem aceleração de áudio (causa travamentos)
- Chunks de 10 minutos para evitar travamentos
- Paralelismo real com múltiplos processos
- Logs detalhados de progresso
- Otimização máxima de CPU - TODOS OS CORES
"""

import sys
import json
import logging
import whisper
from text_processor import TextProcessor, TextProcessingRules
from pydub import AudioSegment
import os
import multiprocessing
import torch
import numpy as np
# Adicionando pyannote para diarização
from pyannote.audio import Pipeline as PyannotePipeline
from huggingface_hub import hf_hub_download
import concurrent.futures
import subprocess
import threading

# Função utilitária para carregar pipeline de diarização

def load_pyannote_pipeline():
    """Pipeline básico do pyannote.audio sem configurações customizadas."""
    hf_token = os.environ.get("HUGGINGFACE_TOKEN")
    if not hf_token:
        raise RuntimeError("Variável de ambiente HUGGINGFACE_TOKEN não definida.")
    
    # Usar pipeline padrão sem configurações customizadas
    pipeline = PyannotePipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", 
        use_auth_token=hf_token
    )
    
    device = torch.device("cpu")
    pipeline.to(device)
    return pipeline

# Configurar para usar TODOS os CPUs disponíveis
def setup_cpu_optimization():
    """Configura otimização máxima de CPU para 8 vCPUs do CCX33."""
    cpu_count = min(8, multiprocessing.cpu_count())  # CCX33 tem 8 vCPUs
    
    # Configurações agressivas para máxima velocidade
    os.environ["OMP_NUM_THREADS"] = str(cpu_count)
    os.environ["MKL_NUM_THREADS"] = str(cpu_count)
    os.environ["OPENBLAS_NUM_THREADS"] = str(cpu_count)
    os.environ["NUMEXPR_NUM_THREADS"] = str(cpu_count)
    os.environ["VECLIB_MAXIMUM_THREADS"] = str(cpu_count)
    os.environ["BLIS_NUM_THREADS"] = str(cpu_count)
    os.environ["MKL_DYNAMIC"] = "FALSE"
    os.environ["OMP_DYNAMIC"] = "FALSE"
    os.environ["GOMP_CPU_AFFINITY"] = "0-7"  # Usar todos os 8 cores
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"
    
    # Configurações PyTorch para CPU
    torch.set_num_threads(cpu_count)
    torch.set_num_interop_threads(cpu_count)
    
    return cpu_count

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def basic_text_processor():
    rules = TextProcessingRules(
        capitalize_sentences=True,
        fix_spaces=True,
        ensure_final_punctuation=True,
        normalize_numbers=False,
        fix_common_errors=False,
        normalize_punctuation=True,
        capitalize_words=['Brasil', 'São Paulo', 'Rio de Janeiro'],
        common_replacements={}
    )
    return TextProcessor(rules)

def split_audio_streaming(file_path, chunk_duration_ms=30 * 60 * 1000):  # 30 minutos para CCX33
    """Corta o áudio em blocos de 30 minutos (otimizado para CCX33 com 8 vCPUs)."""
    audio = AudioSegment.from_file(file_path)
    for i in range(0, len(audio), chunk_duration_ms):
        chunk = audio[i:i + chunk_duration_ms]
        chunk_path = f"{file_path}_chunk_{i // chunk_duration_ms}.mp3"
        chunk.export(chunk_path, format="mp3", bitrate="64k")  # Bitrate baixo = mais rápido
        yield chunk_path, i // chunk_duration_ms

def extract_audio_if_needed(input_path):
    """Extrai áudio em 8kHz mono para máxima velocidade."""
    audio_exts = ['.wav', '.mp3', '.flac', '.ogg', '.m4a']
    video_exts = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
    ext = os.path.splitext(input_path)[1].lower()
    if ext in audio_exts:
        return input_path
    if ext in video_exts:
        output_path = input_path + '_audio.wav'
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-vn', '-acodec', 'pcm_s16le', '-ar', '8000', '-ac', '1',  # 8kHz mono
            '-af', 'highpass=f=200,lowpass=f=3000',  # Filtro para reduzir ruído
            output_path
        ]
        subprocess.run(cmd, check=True)
        return output_path
    return input_path

# Função para transcrever um chunk (para uso em paralelo)
def transcribe_chunk(args):
    chunk_path, chunk_index, model, text_processor = args
    result = model.transcribe(
        chunk_path,
        language="pt",
        word_timestamps=True,
        initial_prompt=(
            "Transcreva em português do Brasil. "
            "Use linguagem formal e evite redundâncias. "
            "Corrija erros comuns e normalize números."
        ),
        fp16=False,
        verbose=False,
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        logprob_threshold=-1.0,
        no_speech_threshold=0.6
    )
    chunk_start_time = chunk_index * 30 * 60
    segments = []
    for segment in result.get("segments", []):
        segment["start"] += chunk_start_time
        segment["end"] += chunk_start_time
        processed_text = text_processor.process(segment["text"])
        segment["text"] = processed_text
        segments.append(segment)
    try:
        os.remove(chunk_path)
    except Exception:
        pass
    return segments

def diarize_audio(audio_path, pipeline=None, max_duration_minutes=30):
    """Diarização com fallback automático para segmentação simples."""
    try:
        if pipeline is None:
            pipeline = load_pyannote_pipeline()
        
        audio = AudioSegment.from_file(audio_path)
        duration_minutes = len(audio) / (1000 * 60)
        
        logger.info(f"🚀 Diarização iniciada para {duration_minutes:.1f}min de áudio")
        
        diarization_done = threading.Event()
        def progress_log():
            if not diarization_done.is_set():
                logger.info("⚡ Diarização em andamento...")
                threading.Timer(30, progress_log).start()
        
        progress_log()
        
        # Tentar diarização com timeout
        timeout_seconds = min(duration_minutes * 60, 1800)
        logger.info(f"⏱️ Timeout: {timeout_seconds/60:.1f} minutos")
        
        diarization = pipeline(audio_path)
        diarized_segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            diarized_segments.append({
                'speaker': speaker,
                'start': float(turn.start),
                'end': float(turn.end)
            })
        
        diarization_done.set()
        logger.info(f"⚡ Diarização concluída: {len(diarized_segments)} segmentos")
        return diarized_segments
        
    except Exception as e:
        logger.error(f"❌ Erro na diarização: {e}")
        logger.info("🔄 Usando fallback: segmentação simples por tempo")
        return create_simple_segments(audio_path, segment_duration=60)

def create_simple_segments(audio_path, segment_duration=30):
    """Cria segmentos simples baseados em tempo quando diarização falha."""
    audio = AudioSegment.from_file(audio_path)
    duration_seconds = len(audio) / 1000
    segments = []
    
    for i in range(0, int(duration_seconds), segment_duration):
        segments.append({
            'speaker': f'SPEAKER_{i//segment_duration:02d}',
            'start': float(i),
            'end': float(min(i + segment_duration, duration_seconds))
        })
    
    return segments

def align_segments_with_speakers(whisper_segments, diarized_segments):
    """Alinha os segmentos do Whisper com os segmentos diarizados por maior interseção temporal."""
    def find_best_speaker(start, end):
        best_speaker = None
        max_overlap = 0
        for seg in diarized_segments:
            overlap = max(0, min(end, seg['end']) - max(start, seg['start']))
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = seg['speaker']
        return best_speaker or 'SPEAKER_00'

    aligned = []
    for seg in whisper_segments:
        speaker = find_best_speaker(seg['start'], seg['end'])
        aligned.append({
            'speaker': speaker,
            'start': seg['start'],
            'end': seg['end'],
            'text': seg['text']
        })
    return aligned

def transcribe_audio(audio_path):
    try:
        # NOVO: extrair áudio se necessário
        original_path = audio_path
        audio_path = extract_audio_if_needed(audio_path)
        temp_audio = (audio_path != original_path) and audio_path.endswith('_audio.wav')
        
        # Configurar otimização máxima de CPU
        cpu_count = setup_cpu_optimization()
        logger.info(f"🚀 Otimização de CPU configurada: {cpu_count} cores disponíveis")
        
        text_processor = basic_text_processor()
        logger.info("✅ Text processor inicializado")
        
        logger.info("🔄 Carregando modelo Whisper Small...")
        model = whisper.load_model("small")
        logger.info("✅ Modelo Whisper Small carregado com sucesso")

        # --- Diarização com fallback automático ---
        skip_diarization = os.environ.get("SKIP_DIARIZATION", "false").lower() == "true"
        
        if skip_diarization:
            logger.info("⏭️ Pulando diarização (SKIP_DIARIZATION=true). Usando segmentação simples...")
            diarized_segments = create_simple_segments(audio_path)
        else:
            logger.info("🔊 Executando diarização de locutores (pyannote, CPU)...")
            try:
                diarization_pipeline = load_pyannote_pipeline()
                diarized_segments = diarize_audio(audio_path, diarization_pipeline)
            except Exception as e:
                logger.error(f"❌ Erro ao carregar pipeline de diarização: {e}")
                logger.info("🔄 Usando segmentação simples como fallback...")
                diarized_segments = create_simple_segments(audio_path)

        logger.info(f"✅ Diarização concluída: {len(diarized_segments)} segmentos encontrados")
        chunk_args = []
        logger.info("📂 Dividindo áudio em chunks de 15 minutos...")
        for chunk_path, chunk_index in split_audio_streaming(audio_path):
            chunk_args.append((chunk_path, chunk_index, model, text_processor))
        whisper_segments = []
        # Processar chunks em paralelo usando todos os núcleos disponíveis
        logger.info(f"⚡ Transcrevendo {len(chunk_args)} chunks em paralelo com {cpu_count} workers...")
        with concurrent.futures.ProcessPoolExecutor(max_workers=cpu_count) as executor:
            for chunk_result in executor.map(transcribe_chunk, chunk_args):
                whisper_segments.extend(chunk_result)
        logger.info(f"✅ Transcrição paralela concluída: {len(whisper_segments)} segmentos")
        # --- Alinhar segmentos do Whisper com locutores ---
        logger.info("🔗 Alinhando segmentos da transcrição com locutores...")
        aligned = align_segments_with_speakers(whisper_segments, diarized_segments)
        # Mapear SPEAKER_XX para LOCUTOR_X
        speaker_map = {}
        speaker_count = 1
        formatted_segments = []
        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            return f"{h:02}:{m:02}:{s:02}"
        for seg in aligned:
            spk = seg['speaker']
            if spk not in speaker_map:
                speaker_map[spk] = f"LOCUTOR_{speaker_count}"
                speaker_count += 1
            locutor = speaker_map[spk]
            start_str = format_time(seg['start'])
            formatted_segments.append(f"{start_str} {locutor}: {seg['text']}")
        formatted_text = "\n".join(formatted_segments)
        logger.info(f"🎉 Transcrição e diarização concluídas!")
        logger.info(f"📊 Resumo: {len(chunk_args)} chunks, {len(aligned)} segmentos, {len(formatted_text)} caracteres")
        result = json.dumps({
            "status": "success",
            "text": formatted_text.strip(),
            "segments": aligned,
            "chunks": len(chunk_args),
            "language": "pt"
        }, ensure_ascii=False)
        # Limpeza automática do áudio temporário extraído
        if temp_audio and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"🗑️ Áudio temporário removido: {audio_path}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao remover áudio temporário: {e}")
        return result
    except Exception as e:
        # Limpeza também em caso de erro
        if 'audio_path' in locals() and 'temp_audio' in locals() and temp_audio and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"🗑️ Áudio temporário removido após erro: {audio_path}")
            except Exception:
                pass
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stdout.buffer.write(json.dumps({
            "status": "error",
            "error": "Please provide the audio file path"
        }, ensure_ascii=False).encode('utf-8'))
        sys.exit(1)

    audio_path = sys.argv[1]
    output = transcribe_audio(audio_path)
    sys.stdout.buffer.write(output.encode('utf-8')) 