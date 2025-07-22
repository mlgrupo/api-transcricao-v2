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

def split_audio_streaming(file_path, chunk_duration_ms=15 * 60 * 1000):
    """Corta o áudio em blocos de X segundos (default: 15min para maior eficiência em CPU)."""
    audio = AudioSegment.from_file(file_path)
    for i in range(0, len(audio), chunk_duration_ms):
        chunk = audio[i:i + chunk_duration_ms]
        chunk_path = f"{file_path}_chunk_{i // chunk_duration_ms}.mp3"
        chunk.export(chunk_path, format="mp3")
        yield chunk_path, i // chunk_duration_ms

def extract_audio_if_needed(input_path):
    """Se for vídeo, extrai o áudio para WAV mono 16kHz e retorna o novo caminho. Se já for áudio, retorna o original."""
    audio_exts = ['.wav', '.mp3', '.flac', '.ogg', '.m4a']
    video_exts = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
    ext = os.path.splitext(input_path)[1].lower()
    if ext in audio_exts:
        return input_path
    if ext in video_exts:
        output_path = input_path + '_audio.wav'
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_path
        ]
        subprocess.run(cmd, check=True)
        return output_path
    # Se extensão desconhecida, tenta processar como áudio
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
    chunk_start_time = chunk_index * 15 * 60
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

        # --- Diarização do áudio completo ---
        skip_diarization = os.environ.get("SKIP_DIARIZATION", "false").lower() == "true"
        
        if skip_diarization:
            logger.info("⏭️ Pulando diarização (SKIP_DIARIZATION=true). Usando segmentação simples...")
            diarized_segments = create_simple_segments(audio_path)
        else:
            logger.info("🔊 Executando diarização de locutores (pyannote, CPU)...")
            diarization_pipeline = load_pyannote_pipeline()
            diarized_segments = diarize_audio(audio_path, diarization_pipeline)

        logger.info(f"✅ Diarização concluída: {len(diarized_segments)} segmentos encontrados")
        
        chunk_args = []
        logger.info("📂 Dividindo áudio em chunks de 15 minutos...")
        for chunk_path, chunk_index in split_audio_streaming(audio_path):
            chunk_args.append((chunk_path, chunk_index, model, text_processor))
        
        whisper_segments = []
        # Processar chunks em paralelo usando apenas 1 worker no servidor
        logger.info(f"⚡ Transcrevendo {len(chunk_args)} chunks com 1 worker (sequencial)...")
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            for chunk_result in executor.map(transcribe_chunk, chunk_args):
                whisper_segments.extend(chunk_result)
        logger.info(f"✅ Transcrição concluída: {len(whisper_segments)} segmentos")

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
        logger.error(f"❌ Erro na transcrição: {e}")
        # Limpeza em caso de erro
        if temp_audio and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"🗑️ Áudio temporário removido após erro: {audio_path}")
            except Exception:
                pass
        raise

def load_pyannote_pipeline():
    """Carrega o pipeline de diarização do pyannote usando o token HuggingFace."""
    hf_token = os.environ.get("HUGGINGFACE_TOKEN")
    if not hf_token:
        raise RuntimeError("Variável de ambiente HUGGINGFACE_TOKEN não definida. Cadastre seu token do HuggingFace.")
    pipeline = PyannotePipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=hf_token)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(device)
    return pipeline

def setup_cpu_optimization():
    """Configura otimização máxima de CPU"""
    # Detectar número de CPUs
    cpu_count = multiprocessing.cpu_count()
    
    # Configurar PyTorch para usar todos os cores
    try:
        if torch.cuda.is_available():
            torch.set_num_threads(cpu_count)
            logger.info(f"PyTorch CUDA configurado para {cpu_count} threads")
        else:
            # Para CPU, usar todos os cores disponíveis
            torch.set_num_threads(cpu_count)
            torch.set_num_interop_threads(cpu_count)
            logger.info(f"PyTorch CPU configurado para {cpu_count} threads")
    except Exception as e:
        logger.warning(f"Erro ao configurar PyTorch threads: {e}")
        pass
    
    # Configurar NumPy para usar todos os cores (compatibilidade)
    try:
        np.set_num_threads(cpu_count)
        logger.info(f"NumPy configurado para {cpu_count} threads")
    except AttributeError:
        # Versões mais antigas do NumPy não têm set_num_threads
        logger.info(f"NumPy não suporta set_num_threads, usando configuração padrão")
        pass
    
    # Configurar variáveis de ambiente para bibliotecas BLAS
    os.environ['OMP_NUM_THREADS'] = str(cpu_count)
    os.environ['MKL_NUM_THREADS'] = str(cpu_count)
    os.environ['OPENBLAS_NUM_THREADS'] = str(cpu_count)
    os.environ['VECLIB_MAXIMUM_THREADS'] = str(cpu_count)
    os.environ['NUMEXPR_NUM_THREADS'] = str(cpu_count)
    os.environ['BLIS_NUM_THREADS'] = str(cpu_count)
    
    # Desabilitar thread dinâmico para melhor performance
    os.environ['MKL_DYNAMIC'] = 'FALSE'
    os.environ['OMP_DYNAMIC'] = 'FALSE'
    
    return cpu_count

def diarize_audio(audio_path, pipeline=None):
    """Executa diarização e retorna lista de segmentos: [{'speaker': 'SPEAKER_00', 'start': float, 'end': float}]"""
    if pipeline is None:
        pipeline = load_pyannote_pipeline()
    diarization = pipeline(audio_path)
    diarized_segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        diarized_segments.append({
            'speaker': speaker,
            'start': float(turn.start),
            'end': float(turn.end)
        })
    return diarized_segments

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

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python transcribe.py <caminho_do_audio>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    try:
        result = transcribe_audio(audio_path)
        print(result)
    except Exception as e:
        error_result = json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False)
        print(error_result)
        sys.exit(1) 