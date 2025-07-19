#!/usr/bin/env python3
"""
Sistema de Transcrição 100% GRATUITO
FOCO: Whisper + Diarização gratuita, sem tokens, funciona offline
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
import time

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize

# Import da diarização gratuita
try:
    from diarization import diarize_audio_free, DiarizationSegment
    DIARIZATION_AVAILABLE = True
except ImportError:
    DIARIZATION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Diarização não disponível - será usada apenas transcrição")

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
    
    def process(self, audio: AudioSegment) -> AudioSegment:
        logger.info("🔧 Pré-processando áudio...")
        try:
            # Normalização
            audio = normalize(audio, headroom=0.1)
            
            # Conversão para formato padrão
            audio = audio.set_frame_rate(self.sample_rate).set_channels(self.channels)
            
            # Amplificar se muito baixo
            if audio.dBFS < -30:
                audio = audio + (25 - abs(audio.dBFS))
            
            logger.info(f"✅ Pré-processamento concluído (dBFS: {audio.dBFS:.1f})")
            return audio
        except Exception as e:
            logger.warning(f"⚠️ Erro no pré-processamento: {e}")
            return audio

class TextPostProcessor:
    def clean_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        
        # Remover espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        # Remover caracteres problemáticos
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)]', '', text)
        
        return text.strip()
    
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        """Formatar timestamp no formato [HH:MM:SS - HH:MM:SS]"""
        def seconds_to_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        start_str = seconds_to_time(start_time)
        end_str = seconds_to_time(end_time)
        return f"[{start_str} - {end_str}]"
    
    def format_speaker_name(self, speaker: str) -> str:
        """Formatar nome do speaker"""
        if speaker.startswith("SPEAKER_"):
            try:
                number = int(speaker.split("_")[1]) + 1
                return f"Speaker {number:02d}"
            except:
                return speaker
        return speaker

def is_invalid_transcription(text: str) -> bool:
    """Detectar transcrições inválidas ou de baixa qualidade"""
    if not text or len(text.strip()) < 2:
        return True
    
    text_lower = text.lower().strip()
    
    # Frases que indicam erro na transcrição
    bad_indicators = [
        "transcreva com a maior precisão",
        "áudio em português brasileiro",
        "transcreva", "transcrição",
        "por favor", "muito obrigado",
        "não sei", "não entendi"
    ]
    
    for indicator in bad_indicators:
        if indicator in text_lower:
            return True
    
    # Detectar repetições excessivas
    words = text_lower.split()
    if len(words) > 5:
        word_counts = {}
        for word in words:
            if len(word) > 3:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        for word, count in word_counts.items():
            if count > 8:  # Palavra repetida mais de 8 vezes
                return True
    
    return False

class WhisperTranscriber:
    def __init__(self):
        self.model = None
        self.model_size = "large-v2"  # Melhor qualidade
    
    def load_model(self, force_size=None):
        """Carregar modelo Whisper"""
        model_size = force_size or self.model_size
        
        if self.model is None or force_size:
            logger.info(f"🤖 Carregando Whisper {model_size}...")
            try:
                self.model = whisper.load_model(model_size, device="cpu")
                logger.info(f"✅ Modelo {model_size} carregado com sucesso")
            except Exception as e:
                if model_size != "medium":
                    logger.warning(f"⚠️ Erro ao carregar {model_size}, tentando 'medium': {e}")
                    self.model = whisper.load_model("medium", device="cpu")
                    self.model_size = "medium"
                else:
                    raise e
        
        return self.model
    
    def transcribe_segment(self, audio_path: str, max_attempts=3) -> str:
        """Transcrever um segmento de áudio"""
        model = self.load_model()
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"🎯 Tentativa {attempt + 1}/{max_attempts}")
                
                # Configurações progressivamente mais simples
                if attempt == 0:
                    # Primeira tentativa: máxima qualidade
                    result = model.transcribe(
                        audio_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.1,
                        compression_ratio_threshold=1.8,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.2,
                        initial_prompt="Transcrição em português brasileiro."
                    )
                elif attempt == 1:
                    # Segunda tentativa: configuração média
                    result = model.transcribe(
                        audio_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.2,
                        no_speech_threshold=0.3
                    )
                else:
                    # Última tentativa: configuração simples
                    result = model.transcribe(
                        audio_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.3
                    )
                
                transcription = result["text"].strip()
                
                if transcription and not is_invalid_transcription(transcription):
                    logger.info(f"✅ Transcrição válida obtida na tentativa {attempt + 1}")
                    return transcription
                else:
                    logger.warning(f"❌ Transcrição inválida na tentativa {attempt + 1}")
                    
            except Exception as e:
                logger.warning(f"❌ Erro na tentativa {attempt + 1}: {e}")
                
                # Se erro de memória, tentar modelo menor
                if "memory" in str(e).lower() and self.model_size != "medium":
                    logger.info("🔄 Tentando modelo menor devido a limitação de memória...")
                    self.load_model("medium")
        
        return ""

class FreeTranscriptionProcessor:
    def __init__(self):
        self.audio_preprocessor = AudioPreprocessor()
        self.text_processor = TextPostProcessor()
        self.transcriber = WhisperTranscriber()
    
    def create_simple_diarization(self, duration: float, num_speakers=2) -> List[DiarizationSegment]:
        """Criar diarização simples quando a avançada não está disponível"""
        segments = []
        
        if duration <= 60:  # 1 minuto
            segments.append(DiarizationSegment(0, duration, "SPEAKER_00"))
        else:
            # Dividir em segmentos alternados
            segment_duration = min(30, duration / num_speakers)  # Máximo 30s por segmento
            current_time = 0
            speaker_id = 0
            
            while current_time < duration:
                end_time = min(current_time + segment_duration, duration)
                segments.append(DiarizationSegment(
                    current_time, end_time, f"SPEAKER_{speaker_id:02d}"
                ))
                current_time = end_time
                speaker_id = (speaker_id + 1) % num_speakers
        
        return segments
    
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        """Transcrever áudio com diarização gratuita"""
        logger.info(f"🎯 Iniciando transcrição gratuita: {audio_path}")
        temp_files = []
        
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Carregar e analisar áudio
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            duration_min = duration / 60.0
            
            logger.info(f"📊 Duração: {duration_min:.1f} minutos")
            
            # Para áudios muito longos, usar estratégia simples
            if duration > 7200:  # 2 horas
                logger.warning("⚠️ Áudio muito longo - usando transcrição direta")
                return self.direct_transcription(audio_path)
            
            # Pré-processar áudio
            audio = self.audio_preprocessor.process(audio)
            
            # Salvar áudio processado
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                processed_audio_path = temp_file.name
                temp_files.append(processed_audio_path)
            
            # Tentar diarização
            if DIARIZATION_AVAILABLE and duration > 30:  # Só usar diarização se > 30s
                try:
                    logger.info("🎯 Aplicando diarização gratuita...")
                    diarization_segments = diarize_audio_free(processed_audio_path)
                    
                    if diarization_segments:
                        unique_speakers = set(seg.speaker for seg in diarization_segments)
                        logger.info(f"✅ Diarização: {len(diarization_segments)} segmentos, {len(unique_speakers)} speakers")
                        
                        return self.transcribe_with_diarization(
                            audio, diarization_segments, temp_files
                        )
                    else:
                        logger.warning("⚠️ Diarização não retornou segmentos")
                        
                except Exception as e:
                    logger.warning(f"❌ Diarização falhou: {e}")
            
            # Fallback: diarização simples ou transcrição direta
            if duration <= 30:
                logger.info("⚡ Áudio curto - transcrição direta")
                return self.direct_transcription(processed_audio_path)
            else:
                logger.info("🔄 Usando diarização simples")
                simple_segments = self.create_simple_diarization(duration, num_speakers=3)
                return self.transcribe_with_diarization(
                    audio, simple_segments, temp_files
                )
                
        except Exception as e:
            logger.error(f"💥 Erro crítico: {e}")
            return self.direct_transcription(audio_path)
        finally:
            # Limpeza
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
    
    def direct_transcription(self, audio_path: str) -> str:
        """Transcrição direta sem diarização"""
        logger.info("🎯 Transcrição direta iniciada")
        
        try:
            transcription = self.transcriber.transcribe_segment(audio_path)
            
            if transcription:
                # Criar formato com timestamp simples
                audio = AudioSegment.from_file(audio_path)
                duration = len(audio) / 1000.0
                
                timestamp = self.text_processor.format_timestamp(0, duration)
                formatted_text = self.text_processor.clean_text(transcription)
                
                return f"{timestamp} Speaker 01:\n{formatted_text}"
            else:
                return "Não foi possível transcrever este áudio."
                
        except Exception as e:
            logger.error(f"❌ Erro na transcrição direta: {e}")
            return f"Erro na transcrição: {str(e)}"
    
    def transcribe_with_diarization(self, audio: AudioSegment, segments: List, temp_files: List) -> str:
        """Transcrever com segmentos de diarização"""
        logger.info(f"🚀 Transcrevendo {len(segments)} segmentos")
        
        formatted_segments = []
        valid_transcriptions = 0
        total_segments = len(segments)
        
        for i, seg in enumerate(segments):
            try:
                # Extrair segmento de áudio
                start_ms = max(0, int(seg.start * 1000))
                end_ms = min(len(audio), int(seg.end * 1000))
                
                if end_ms <= start_ms or (end_ms - start_ms) < 500:  # Muito curto
                    logger.warning(f"⚠️ Segmento {i+1} muito curto, pulando...")
                    continue
                
                seg_audio = audio[start_ms:end_ms]
                
                # Salvar segmento temporário
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                    seg_audio.export(seg_file.name, format='wav')
                    seg_path = seg_file.name
                    temp_files.append(seg_path)
                
                # Transcrever segmento
                transcription_text = self.transcriber.transcribe_segment(seg_path)
                
                if transcription_text.strip():
                    processed_text = self.text_processor.clean_text(transcription_text)
                    
                    if processed_text.strip():
                        timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                        speaker_name = self.text_processor.format_speaker_name(seg.speaker)
                        
                        formatted_segments.append(f"{timestamp} {speaker_name}:\n{processed_text}")
                        valid_transcriptions += 1
                        
                        logger.info(f"✅ Segmento {i+1}/{total_segments}: {len(processed_text)} chars")
                    else:
                        logger.warning(f"⚠️ Segmento {i+1}: texto vazio após processamento")
                else:
                    logger.warning(f"⚠️ Segmento {i+1}: sem transcrição")
                
            except Exception as e:
                logger.warning(f"❌ Erro no segmento {i+1}: {e}")
                continue
        
        if formatted_segments:
            success_rate = valid_transcriptions / total_segments
            result = "\n\n".join(formatted_segments)
            logger.info(f"🎉 Transcrição concluída: {valid_transcriptions}/{total_segments} ({success_rate:.1%} sucesso)")
            return result
        else:
            logger.error("❌ Nenhum segmento foi transcrito com sucesso")
            return self.direct_transcription(audio_path)

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
        processor = FreeTranscriptionProcessor()
        result = processor.transcribe_audio(audio_path, output_dir)
        
        # Salvar arquivo se solicitado
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"💾 Transcrição salva: {output_file}")
        
        # Output JSON
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "free_whisper_diarization",
            "timestamp": datetime.now().isoformat(),
            "diarization_available": DIARIZATION_AVAILABLE
        }
        
        print(json.dumps(output, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"💥 Erro na execução: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()