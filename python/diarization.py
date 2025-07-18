#!/usr/bin/env python3
"""
Sistema de Transcrição com TIMEOUT FLEXÍVEL
CONFIGURÁVEL: SEM timeout OU timeout 4x maior via variável de ambiente
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

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== CONFIGURAÇÃO DE TIMEOUT ==========
# Defina o comportamento via variável de ambiente:
# export TRANSCRIPTION_TIMEOUT_MODE="none"     # SEM timeout (padrão)
# export TRANSCRIPTION_TIMEOUT_MODE="4x"       # Timeout 4x o tamanho do áudio
# export TRANSCRIPTION_TIMEOUT_MODE="custom"   # Timeout customizado
# export CUSTOM_TIMEOUT_MULTIPLIER="6"         # Para modo custom: 6x o áudio

TIMEOUT_MODE = os.environ.get("TRANSCRIPTION_TIMEOUT_MODE", "none").lower()
CUSTOM_MULTIPLIER = float(os.environ.get("CUSTOM_TIMEOUT_MULTIPLIER", "4"))

logger.info(f"🎯 MODO DE TIMEOUT CONFIGURADO: {TIMEOUT_MODE.upper()}")

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Timeout no processamento")

class FlexibleTimeoutManager:
    """Gerenciador flexível de timeouts"""
    
    def __init__(self):
        self.mode = TIMEOUT_MODE
        self.custom_multiplier = CUSTOM_MULTIPLIER
        
    def should_use_timeout(self, audio_duration_minutes: float) -> bool:
        """Decide se deve usar timeout baseado na configuração"""
        if self.mode == "none":
            return False
        elif self.mode in ["4x", "custom"]:
            return True
        else:
            # Padrão: sem timeout
            return False
    
    def calculate_timeout(self, audio_duration_minutes: float) -> int:
        """Calcula timeout baseado na configuração"""
        if not self.should_use_timeout(audio_duration_minutes):
            return 0  # Sem timeout
        
        if self.mode == "4x":
            multiplier = 4
        elif self.mode == "custom":
            multiplier = self.custom_multiplier
        else:
            multiplier = 4
        
        # Cálculo: X minutos por minuto de áudio + buffer de 30 min
        timeout_minutes = int(audio_duration_minutes * multiplier) + 30
        
        # Limites: mínimo 30 min, máximo 12 horas
        timeout_minutes = max(30, min(720, timeout_minutes))
        
        return timeout_minutes
    
    def log_timeout_info(self, audio_duration_minutes: float, chunk_duration_minutes: float = None):
        """Log informações sobre timeout configurado"""
        if not self.should_use_timeout(audio_duration_minutes):
            logger.info(f"⏳ CONFIGURADO: SEM TIMEOUT - paciência infinita")
        else:
            timeout_min = self.calculate_timeout(audio_duration_minutes)
            chunk_timeout = self.calculate_timeout(chunk_duration_minutes) if chunk_duration_minutes else None
            
            logger.info(f"⏰ CONFIGURADO: Timeout {self.mode.upper()}")
            logger.info(f"   📊 Áudio {audio_duration_minutes:.1f}min → Timeout {timeout_min}min")
            if chunk_timeout:
                logger.info(f"   🔗 Chunk {chunk_duration_minutes:.1f}min → Timeout {chunk_timeout}min")

class AudioPreprocessor:
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
    
    def process(self, audio: AudioSegment) -> AudioSegment:
        logger.info("🔧 Pré-processando áudio...")
        try:
            audio = normalize(audio, headroom=0.1)
            audio = audio.set_frame_rate(self.sample_rate).set_channels(self.channels)
            if audio.dBFS < -30:
                audio = audio + (25 - abs(audio.dBFS))
            logger.info(f"✅ Pré-processamento concluído")
            return audio
        except Exception as e:
            logger.warning(f"Erro no pré-processamento: {e}")
            return audio

class TextPostProcessor:
    def clean_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        start_h, start_m, start_s = int(start_time // 3600), int((start_time % 3600) // 60), int(start_time % 60)
        end_h, end_m, end_s = int(end_time // 3600), int((end_time % 3600) // 60), int(end_time % 60)
        return f"[{start_h:02d}:{start_m:02d}:{start_s:02d} - {end_h:02d}:{end_m:02d}:{end_s:02d}]"
    
    def format_speaker_name(self, speaker: str) -> str:
        if speaker.startswith("SPEAKER_"):
            try:
                number = int(speaker.split("_")[1]) + 1
                return f"Speaker {number:02d}"
            except:
                return speaker
        return speaker

def is_invalid_transcription(text: str) -> bool:
    """Detecção de transcrições inválidas"""
    text_lower = text.lower().strip()
    
    bad_indicators = [
        "transcreva com a maior precisão",
        "áudio em português brasileiro",
        "transcreva", "transcrição"
    ]
    
    for indicator in bad_indicators:
        if indicator in text_lower:
            return True
    
    if len(text.strip()) < 2:
        return True
    
    words = text_lower.split()
    if len(words) > 5:
        word_counts = {}
        for word in words:
            if len(word) > 3:
                word_counts[word] = word_counts.get(word, 0) + 1
        for word, count in word_counts.items():
            if count > 8:
                return True
    
    return False

def create_fallback_transcription(audio_path: str) -> str:
    """Fallback ultimate usando apenas Whisper"""
    logger.info("🚨 FALLBACK: Whisper direto")
    
    try:
        # Escolher modelo baseado no modo de timeout
        timeout_manager = FlexibleTimeoutManager()
        
        if timeout_manager.mode == "none":
            model_name = "large-v2"  # Melhor qualidade sem pressa
        else:
            model_name = "medium"    # Mais rápido com timeout
        
        model = whisper.load_model(model_name, device="cpu")
        logger.info(f"🤖 Modelo {model_name} carregado para fallback")
        
        # Aplicar timeout se configurado
        audio_duration = len(AudioSegment.from_file(audio_path)) / 1000.0 / 60.0
        timeout_min = timeout_manager.calculate_timeout(audio_duration)
        
        if timeout_manager.should_use_timeout(audio_duration):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_min * 60)
            logger.info(f"⏰ Fallback com timeout de {timeout_min}min")
        else:
            logger.info("⏳ Fallback SEM TIMEOUT")
        
        result = model.transcribe(
            audio_path,
            language="pt",
            task="transcribe",
            verbose=False,
            fp16=False,
            temperature=0.1
        )
        
        if timeout_manager.should_use_timeout(audio_duration):
            signal.alarm(0)
        
        text = result["text"].strip()
        
        if text and not is_invalid_transcription(text):
            # Criar segmentação simples
            sentences = re.split(r'[.!?]+', text)
            filtered_sentences = [s.strip() for s in sentences if s.strip()]
            
            formatted_segments = []
            segment_duration = 30
            current_time = 0
            speaker_id = 1
            
            for i, sentence in enumerate(filtered_sentences):
                if sentence:
                    end_time = current_time + segment_duration
                    timestamp = f"[{int(current_time//3600):02d}:{int((current_time%3600)//60):02d}:{int(current_time%60):02d} - {int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d}]"
                    speaker = f"Speaker {speaker_id:02d}"
                    formatted_segments.append(f"{timestamp} {speaker}:\n{sentence}.")
                    current_time = end_time
                    
                    if (i + 1) % 3 == 0:
                        speaker_id = (speaker_id % 3) + 1
            
            result_text = "\n\n".join(formatted_segments)
            logger.info("✅ Fallback concluído com sucesso")
            return result_text
        
        return "Não foi possível transcrever este áudio."
        
    except TimeoutException:
        signal.alarm(0)
        logger.error(f"⏰ Timeout no fallback ({timeout_min}min)")
        return "Timeout na transcrição. Arquivo muito complexo ou sistema sobrecarregado."
    except Exception as e:
        if timeout_manager.should_use_timeout(audio_duration):
            signal.alarm(0)
        logger.error(f"❌ Erro no fallback: {e}")
        return f"Erro na transcrição: {str(e)}"

class FlexibleTranscriptionProcessor:
    def __init__(self):
        self.audio_preprocessor = AudioPreprocessor()
        self.text_processor = TextPostProcessor()
        self.timeout_manager = FlexibleTimeoutManager()
        self.model = None
    
    def load_model(self, model_size: str = "large-v2") -> whisper.Whisper:
        if self.model is None:
            logger.info(f"🤖 Carregando modelo Whisper: {model_size}")
            
            # Aplicar timeout no carregamento se configurado
            if self.timeout_manager.mode != "none":
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(600)  # 10 min para carregar
                logger.info("⏰ Carregamento com timeout de 10min")
            else:
                logger.info("⏳ Carregamento SEM TIMEOUT")
            
            try:
                self.model = whisper.load_model(model_size, device="cpu")
                if self.timeout_manager.mode != "none":
                    signal.alarm(0)
                logger.info("✅ Modelo carregado com sucesso")
                
            except TimeoutException:
                signal.alarm(0)
                logger.warning("⏰ Timeout no carregamento - tentando modelo menor")
                self.model = whisper.load_model("medium", device="cpu")
                logger.info("✅ Modelo 'medium' carregado")
            except Exception as e:
                if self.timeout_manager.mode != "none":
                    signal.alarm(0)
                logger.error(f"❌ Erro ao carregar {model_size}: {e}")
                self.model = whisper.load_model("medium", device="cpu")
                logger.info("✅ Modelo 'medium' carregado como fallback")
        
        return self.model
    
    def transcribe_segment_flexible(self, model, seg_path: str, segment_duration_min: float) -> str:
        """Transcrição com timeout flexível baseado na configuração"""
        
        # Calcular timeout para este segmento
        timeout_min = self.timeout_manager.calculate_timeout(segment_duration_min)
        use_timeout = self.timeout_manager.should_use_timeout(segment_duration_min)
        
        for attempt in range(3):
            try:
                if use_timeout:
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(timeout_min * 60)
                    logger.info(f"🎯 Tentativa {attempt + 1} com timeout de {timeout_min}min")
                else:
                    logger.info(f"🎯 Tentativa {attempt + 1} SEM TIMEOUT")
                
                # Configuração baseada na tentativa
                if attempt == 0:
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.1,
                        compression_ratio_threshold=1.8,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.2,
                        initial_prompt="Transcrição em português brasileiro.",
                        word_timestamps=True
                    )
                elif attempt == 1:
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.2,
                        no_speech_threshold=0.3
                    )
                else:
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.3
                    )
                
                if use_timeout:
                    signal.alarm(0)
                
                transcription = result["text"].strip()
                
                if not is_invalid_transcription(transcription):
                    logger.info(f"✅ Transcrição válida na tentativa {attempt + 1}")
                    return transcription
                else:
                    logger.warning(f"❌ Transcrição inválida na tentativa {attempt + 1}")
                
            except TimeoutException:
                signal.alarm(0)
                logger.warning(f"⏰ Timeout na tentativa {attempt + 1}")
                continue
            except Exception as e:
                if use_timeout:
                    signal.alarm(0)
                logger.warning(f"❌ Erro na tentativa {attempt + 1}: {e}")
                continue
        
        return ""
    
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        logger.info(f"🎯 Iniciando transcrição FLEXÍVEL: {audio_path}")
        temp_files = []
        
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Pré-processar áudio
            audio = AudioSegment.from_file(audio_path)
            audio_duration = len(audio) / 1000.0
            audio_duration_min = audio_duration / 60.0
            
            logger.info(f"📊 Duração: {audio_duration_min:.1f} minutos")
            
            # Log configuração de timeout
            self.timeout_manager.log_timeout_info(audio_duration_min)
            
            # Para áudios muito longos, usar fallback direto
            max_duration = 14400 if self.timeout_manager.mode == "none" else 7200  # 4h ou 2h
            if audio_duration > max_duration:
                logger.warning(f"⚠️ Áudio muito longo - usando fallback")
                return create_fallback_transcription(audio_path)
            
            audio = self.audio_preprocessor.process(audio)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                temp_path = temp_file.name
                temp_files.append(temp_path)
            
            # Tentar diarização
            try:
                logger.info("🎯 Tentando diarização...")
                
                # Import dinâmico para usar a versão flexível
                from diarization import diarize_audio, DiarizationSegment
                diarization_segments = diarize_audio(temp_path)
                
                if diarization_segments:
                    unique_speakers = set(seg.speaker for seg in diarization_segments)
                    logger.info(f"✅ Diarização: {len(diarization_segments)} segmentos, {len(unique_speakers)} speakers")
                    
                    # Continuar com transcrição segmentada
                    return self.transcribe_with_diarization(audio, diarization_segments, temp_files)
                else:
                    raise Exception("Nenhum segmento detectado")
                    
            except Exception as e:
                logger.warning(f"❌ Diarização falhou: {e} - usando fallback")
                return create_fallback_transcription(audio_path)
            
        except Exception as e:
            logger.error(f"💥 Erro crítico: {e}")
            return create_fallback_transcription(audio_path)
        finally:
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
    
    def transcribe_with_diarization(self, audio: AudioSegment, segments: List, temp_files: List) -> str:
        """Transcrição com diarização usando timeout flexível"""
        try:
            model = self.load_model("large-v2")
            formatted_segments = []
            valid_transcriptions = 0
            total_segments = len(segments)
            
            logger.info(f"🚀 Transcrevendo {total_segments} segmentos com timeout {self.timeout_manager.mode.upper()}")
            
            for i, seg in enumerate(segments):
                try:
                    start_ms = max(0, int(seg.start * 1000))
                    end_ms = min(len(audio), int(seg.end * 1000))
                    
                    if end_ms <= start_ms or (end_ms - start_ms) < 500:
                        continue
                    
                    seg_audio = audio[start_ms:end_ms]
                    seg_duration_min = len(seg_audio) / 1000.0 / 60.0
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                        seg_audio.export(seg_file.name, format='wav')
                        seg_path = seg_file.name
                        temp_files.append(seg_path)
                    
                    # Transcrever com timeout flexível
                    transcription_text = self.transcribe_segment_flexible(
                        model, seg_path, seg_duration_min
                    )
                    
                    if transcription_text.strip():
                        processed_text = self.text_processor.clean_text(transcription_text)
                        
                        if processed_text.strip():
                            timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                            speaker_name = self.text_processor.format_speaker_name(seg.speaker)
                            formatted_segments.append(f"{timestamp} {speaker_name}:\n{processed_text}")
                            valid_transcriptions += 1
                    
                    logger.info(f"✅ Segmento {i+1}/{total_segments} concluído")
                    
                except Exception as e:
                    logger.warning(f"❌ Erro no segmento {i+1}: {e}")
                    continue
            
            if formatted_segments:
                success_rate = valid_transcriptions / total_segments
                result = "\n\n".join(formatted_segments)
                logger.info(f"🎉 Transcrição concluída: {valid_transcriptions}/{total_segments} ({success_rate:.1%})")
                return result
            else:
                raise Exception("Nenhum segmento transcrito")
                
        except Exception as e:
            logger.error(f"❌ Erro na transcrição com diarização: {e}")
            raise

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
        processor = FlexibleTranscriptionProcessor()
        result = processor.transcribe_audio(audio_path, output_dir)
        
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"💾 Transcrição salva: {output_file}")
        
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": f"flexible_timeout_{TIMEOUT_MODE}",
            "timestamp": datetime.now().isoformat()
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