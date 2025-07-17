#!/usr/bin/env python3
"""
Sistema de Transcrição Otimizado (Whisper + Diarização)
Mudanças para máxima velocidade:
1. Forçar modelo tiny/base explicitamente
2. Remover reprocessamento desnecessário
3. Otimizar configurações do Whisper
4. Cache do modelo global
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
from concurrent.futures import ProcessPoolExecutor, as_completed  # Mudança: Process em vez de Thread
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

# CACHE GLOBAL DO MODELO - Evitar recarregamentos
_cached_model = None
_cached_model_size = None

def get_whisper_model(model_size: str = "tiny"):
    """Cache global do modelo Whisper"""
    global _cached_model, _cached_model_size
    
    if _cached_model is None or _cached_model_size != model_size:
        logger.info(f"Carregando modelo Whisper: {model_size}")
        
        # FORÇAR o modelo específico - ignorar variáveis de ambiente
        os.environ.pop('WHISPER_MODEL', None)  # Remove se existir
        
        _cached_model = whisper.load_model(
            model_size, 
            device="cpu",
            download_root=None,  # Forçar download padrão
            in_memory=True       # Manter em memória
        )
        _cached_model_size = model_size
        logger.info(f"Modelo {model_size} carregado e cached")
    
    return _cached_model

class AudioPreprocessor:
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        
    def speed_up_audio(self, audio: AudioSegment, speed_factor: float = 2.0) -> AudioSegment:
        """Acelera MAIS o áudio - 2x em vez de 1.5x"""
        try:
            accelerated_audio = audio._spawn(audio.raw_data, overrides={
                "frame_rate": int(audio.frame_rate * speed_factor)
            })
            accelerated_audio = accelerated_audio.set_frame_rate(audio.frame_rate)
            
            logger.info(f"Áudio acelerado: {len(audio)}ms -> {len(accelerated_audio)}ms (speed: {speed_factor}x)")
            return accelerated_audio
        except Exception as e:
            logger.warning(f"Erro ao acelerar áudio: {e}")
            return audio
        
    def process(self, audio: AudioSegment, speed_up: bool = True) -> AudioSegment:
        """Processamento mínimo para máxima velocidade"""
        logger.info("Pré-processamento rápido...")
        
        # Apenas conversões essenciais
        if audio.frame_rate != self.sample_rate:
            audio = audio.set_frame_rate(self.sample_rate)
        if audio.channels != self.channels:
            audio = audio.set_channels(self.channels)
            
        # Acelerar MAIS
        if speed_up:
            audio = self.speed_up_audio(audio, 2.0)  # 2x mais rápido
        
        # Pular normalização para velocidade
        return audio

class TextPostProcessor:
    def __init__(self):
        # Processamento mínimo de texto
        self.basic_cleanup = True
        
    def clean_text(self, text: str) -> str:
        """Limpeza básica e rápida"""
        if not text or not text.strip():
            return ""
        
        # Apenas limpezas essenciais
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Capitalizar primeira letra se necessário
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
            
        return text
    
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        """Timestamp simplificado"""
        start_min = int(start_time // 60)
        start_sec = int(start_time % 60)
        end_min = int(end_time // 60)
        end_sec = int(end_time % 60)
        return f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"

def transcribe_single_segment(segment_data):
    """Função para processamento paralelo de segmentos"""
    seg, audio_path, speed_factor, model_size = segment_data
    
    try:
        # Carregar modelo dentro do processo
        model = get_whisper_model(model_size)
        
        # Carregar e processar segmento
        audio = AudioSegment.from_file(audio_path)
        seg_audio = audio[int(seg.start*1000):int(seg.end*1000)]
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
            seg_audio.export(seg_file.name, format='wav')
            seg_path = seg_file.name
        
        # Configurações ULTRA-RÁPIDAS do Whisper
        result = model.transcribe(
            seg_path,
            language="pt",
            task="transcribe",
            verbose=False,
            fp16=False,
            temperature=0.0,                    # Determinístico
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=False,   # Mais rápido
            beam_size=1,                        # Mínimo para velocidade
            best_of=1,                          # Sem múltiplas tentativas
            patience=1.0,                       # Menos paciência
            suppress_tokens=[-1],               # Suprimir tokens especiais
            without_timestamps=True             # Sem timestamps internos
        )
        
        os.unlink(seg_path)
        
        # Processamento rápido do texto
        text = result["text"].strip()
        text = re.sub(r'\s+', ' ', text)
        
        # Timestamp original
        original_start = seg.start / speed_factor
        original_end = seg.end / speed_factor
        
        start_min = int(original_start // 60)
        start_sec = int(original_start % 60)
        end_min = int(original_end // 60)
        end_sec = int(original_end % 60)
        timestamp = f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"
        
        return f"{timestamp}\n{seg.speaker}: {text}"
        
    except Exception as e:
        logger.error(f"Erro no segmento {seg.speaker}: {e}")
        return f"[ERRO] {seg.speaker}: {str(e)}"

class TranscriptionProcessor:
    def __init__(self):
        self.audio_preprocessor = AudioPreprocessor()
        self.text_processor = TextPostProcessor()
        self.speed_factor = 2.0      # MAIS aceleração
        self.max_workers = 6         # Reduzir para evitar sobrecarga
        self.model_size = "tiny"     # FORÇAR modelo mais rápido

    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        logger.info(f"Transcrição ULTRA-RÁPIDA: {audio_path}")
        logger.info(f"Modelo forçado: {self.model_size}")
        
        try:
            # Pré-carregar modelo
            get_whisper_model(self.model_size)
            
            # Processar áudio
            audio = AudioSegment.from_file(audio_path)
            audio = self.audio_preprocessor.process(audio, speed_up=True)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                temp_path = temp_file.name
            
            # Diarização
            diarization_segments: List[DiarizationSegment] = diarize_audio(temp_path)
            logger.info(f"{len(diarization_segments)} segmentos detectados")
            
            # Preparar dados para processamento paralelo
            segment_data = [
                (seg, temp_path, self.speed_factor, self.model_size)
                for seg in diarization_segments
            ]
            
            # Processamento paralelo REAL com processos
            formatted_segments = []
            max_workers = min(self.max_workers, len(diarization_segments)) or 1
            
            logger.info(f"Processamento paralelo com {max_workers} processos...")
            
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_segment = {
                    executor.submit(transcribe_single_segment, data): data[0]
                    for data in segment_data
                }
                
                for future in as_completed(future_to_segment):
                    segment = future_to_segment[future]
                    try:
                        result = future.result()
                        formatted_segments.append(result)
                    except Exception as e:
                        logger.error(f"Erro no segmento {segment.speaker}: {e}")
                        formatted_segments.append(f"[ERRO] {segment.speaker}: {str(e)}")
            
            os.unlink(temp_path)
            return "\n\n".join(formatted_segments)
            
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
            raise

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    # FORÇAR modelo via argumento se fornecido
    model_size = sys.argv[3] if len(sys.argv) > 3 else "tiny"
    
    try:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
        
        processor = TranscriptionProcessor()
        processor.model_size = model_size  # Forçar modelo
        
        logger.info(f"USANDO MODELO: {model_size}")
        
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
            "processing_type": "fast_diarization_whisper",
            "model_used": model_size,
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