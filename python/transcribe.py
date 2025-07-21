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

# Configurar para usar TODOS os CPUs disponíveis
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

def split_audio_streaming(file_path, chunk_duration_ms=10 * 60 * 1000):
    """Corta o áudio em blocos de X segundos."""
    audio = AudioSegment.from_file(file_path)

    for i in range(0, len(audio), chunk_duration_ms):
        chunk = audio[i:i + chunk_duration_ms]
        chunk_path = f"{file_path}_chunk_{i // chunk_duration_ms}.mp3"
        chunk.export(chunk_path, format="mp3")
        yield chunk_path, i // chunk_duration_ms

def transcribe_audio(audio_path):
    try:
        # Configurar otimização máxima de CPU
        cpu_count = setup_cpu_optimization()
        logger.info(f"🚀 Otimização de CPU configurada: {cpu_count} cores disponíveis")
        
        logger.info(f"🎯 Iniciando transcrição do arquivo: {audio_path}")
        
        text_processor = basic_text_processor()
        logger.info("✅ Text processor inicializado")
        
        logger.info("🔄 Carregando modelo Whisper Medium...")
        model = whisper.load_model("medium")  # Alterar para um modelo maior, se necessário
        logger.info("✅ Modelo Whisper Medium carregado com sucesso")

        full_text = ""
        chunk_count = 0
        all_segments = []

        logger.info("📂 Dividindo áudio em chunks...")
        for chunk_path, chunk_index in split_audio_streaming(audio_path):
            chunk_count += 1
            logger.info(f"🎵 Processando chunk {chunk_count}: {chunk_path}")

            logger.info(f"🔄 Transcrevendo chunk {chunk_count}...")
            result = model.transcribe(
                chunk_path,
                language="pt",
                word_timestamps=True,  # Habilitar timestamps por palavra
                initial_prompt=(
                    "Transcreva em português do Brasil. "
                    "Use linguagem formal e evite redundâncias. "
                    "Corrija erros comuns e normalize números."
                ),
                # Otimizações para usar todos os CPUs
                fp16=False,  # Usar FP32 para melhor compatibilidade com CPU
                verbose=False,  # Reduzir logs do Whisper
                condition_on_previous_text=False,  # Desabilitar para melhor performance
                compression_ratio_threshold=2.4,  # Otimizar threshold
                logprob_threshold=-1.0,  # Otimizar threshold
                no_speech_threshold=0.6  # Otimizar threshold
            )
            logger.info(f"✅ Chunk {chunk_count} transcrito com sucesso")

            # Ajustar timestamps para posição real no áudio
            chunk_start_time = chunk_index * 10 * 60  # 10 minutos por chunk
            logger.info(f"⏰ Ajustando timestamps para chunk {chunk_count} (início: {chunk_start_time}s)")
            
            segments_count = 0
            for segment in result.get("segments", []):
                segment["start"] += chunk_start_time
                segment["end"] += chunk_start_time
                
                # Processar texto do segmento
                processed_text = text_processor.process(segment["text"])
                segment["text"] = processed_text
                
                all_segments.append(segment)
                segments_count += 1

            logger.info(f"📝 Chunk {chunk_count} processado: {segments_count} segmentos")
            logger.info(f"🔧 Aplicando processamento de texto ao chunk {chunk_count}...")

            # Adicionar texto processado ao resultado completo
            processed = text_processor.process(result["text"])
            full_text += processed + "\n"
            
            logger.info(f"✅ Processamento de texto concluído para chunk {chunk_count}")

            try:
                os.remove(chunk_path)
                logger.info(f"🗑️ Arquivo temporário removido: {chunk_path}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao remover arquivo temporário {chunk_path}: {e}")

        logger.info(f"🎉 Transcrição concluída com sucesso!")
        logger.info(f"📊 Resumo: {chunk_count} chunks, {len(all_segments)} segmentos, {len(full_text)} caracteres")
        
        return json.dumps({
            "status": "success",
            "text": full_text.strip(),
            "segments": all_segments,
            "chunks": chunk_count,
            "language": "pt"
        }, ensure_ascii=False)

    except Exception as e:
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