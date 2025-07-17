#!/usr/bin/env python3
"""
Sistema de Transcrição Avançado com Diarização Real de Locutores - Versão Final
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
try:
    from text_processor import TextProcessor, TextProcessingRules
except ImportError:
    # Fallback se módulo não existir
    class TextProcessor:
        def __init__(self, rules): pass
        def process(self, text): return text
    class TextProcessingRules:
        def __init__(self, **kwargs): pass

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
    
    def format_speaker_name(self, speaker: str) -> str:
        """Converte SPEAKER_00 para Speaker 01"""
        if speaker.startswith("SPEAKER_"):
            try:
                number = int(speaker.split("_")[1]) + 1  # Converter 0 para 1, 1 para 2, etc
                return f"Speaker {number:02d}"
            except (IndexError, ValueError):
                return speaker
        return speaker

def is_invalid_transcription(text: str) -> bool:
    """Detecta transcrições inválidas (prompt confusion, repetições, etc.)"""
    text_lower = text.lower().strip()
    
    # Frases que indicam confusão com prompt
    prompt_indicators = [
        "transcreva com a maior precisão possível",
        "transcreva com maior precisão", 
        "transcreva com a maior precisão",
        "áudio em português brasileiro",
        "este é um áudio",
        "a gente tem um áudio em português brasileiro",
        "português brasileiro",
        "transcreva",
        "com a maior precisão",
        "agradeço a você por assistir",  # Outra frase comum de confusão
        "este é o áudio que trouxe",
        "a gente vai ver",
        "ainda não é possível"
    ]
    
    # Verificar confusão de prompt
    for indicator in prompt_indicators:
        if indicator in text_lower:
            return True
    
    # Verificar repetições excessivas (palavras repetidas mais de 5 vezes)
    words = text_lower.split()
    if len(words) > 0:
        word_counts = {}
        for word in words:
            if len(word) > 3:  # Só contar palavras com mais de 3 caracteres
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Se alguma palavra aparece mais de 5 vezes, é suspeito
        for count in word_counts.values():
            if count > 5:
                return True
    
    # Verificar frases muito curtas e genéricas
    generic_phrases = [
        "a gente vai ver",
        "a gente precisa",
        "ainda não é possível",
        "o que você quer dizer",
        "a gente vai fazer"
    ]
    
    if text_lower in generic_phrases:
        return True
    
    # Verificar se é muito curto (menos de 10 caracteres)
    if len(text.strip()) < 10:
        return True
    
    return False

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
                logger.info("Tentando carregar modelo 'base'...")
                self.model = whisper.load_model("base")
                logger.info("Modelo 'base' carregado com sucesso")
        return self.model
    
    def transcribe_segment_safe(self, model, seg_path: str, retry_count: int = 3) -> str:
        """Transcreve um segmento com múltiplas tentativas e filtros rigorosos"""
        for attempt in range(retry_count + 1):
            try:
                # Configurar timeout de 90 segundos por segmento
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(90)
                
                # Configurações diferentes para cada tentativa
                if attempt == 0:
                    # Primeira tentativa: configuração conservadora
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.0,
                        compression_ratio_threshold=2.4,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.6,  # Mais rigoroso
                        condition_on_previous_text=False,
                        initial_prompt=None,
                        suppress_tokens=[-1]  # Suprimir tokens especiais
                    )
                elif attempt == 1:
                    # Segunda tentativa: menos rigoroso para capturar falas baixas
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.2,
                        compression_ratio_threshold=2.4,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.4,
                        condition_on_previous_text=False,
                        initial_prompt=None,
                        suppress_tokens=[-1]
                    )
                elif attempt == 2:
                    # Terceira tentativa: mais permissivo
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.4,
                        compression_ratio_threshold=2.4,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.2,
                        condition_on_previous_text=False,
                        initial_prompt=None,
                        suppress_tokens=[-1]
                    )
                else:
                    # Última tentativa: máxima permissividade
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.6,
                        compression_ratio_threshold=2.4,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.1,
                        condition_on_previous_text=False,
                        initial_prompt=None,
                        suppress_tokens=[-1]
                    )
                
                signal.alarm(0)  # Cancelar timeout
                
                # Verificar se o resultado é válido
                transcription = result["text"].strip()
                
                if is_invalid_transcription(transcription):
                    logger.warning(f"Transcrição inválida detectada (tentativa {attempt + 1}): '{transcription[:50]}...'")
                    if attempt < retry_count:
                        continue
                    return ""  # Retornar vazio se todas as tentativas falharam
                
                # Se chegou aqui, a transcrição é válida
                logger.info(f"Transcrição válida obtida na tentativa {attempt + 1}")
                return transcription
                
            except TimeoutException:
                signal.alarm(0)
                logger.warning(f"Timeout na transcrição do segmento (tentativa {attempt + 1})")
                if attempt < retry_count:
                    continue
                return ""
            except Exception as e:
                signal.alarm(0)
                logger.warning(f"Erro na transcrição do segmento (tentativa {attempt + 1}): {e}")
                if attempt < retry_count:
                    continue
                return ""
        
        return ""
    
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
                
                # Verificar se diarização detectou múltiplos speakers
                unique_speakers = set(seg.speaker for seg in diarization_segments)
                logger.info(f"Speakers únicos detectados: {list(unique_speakers)}")
                
            except Exception as e:
                logger.error(f"Erro na diarização: {e}")
                # Fallback: criar segmentos únicos
                audio_duration = len(audio) / 1000.0
                diarization_segments = [DiarizationSegment(0.0, audio_duration, "SPEAKER_00")]
                logger.info("Usando segmento único como fallback")
            
            # Carregar modelo Whisper
            model = self.load_model("medium")
            
            # Transcrever cada segmento
            formatted_segments = []
            total_segments = len(diarization_segments)
            valid_transcriptions = 0
            
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
                    
                    # Pular segmentos muito curtos (menos de 3 segundos)
                    if len(seg_audio) < 3000:
                        logger.info(f"Pulando segmento muito curto: {len(seg_audio)}ms")
                        continue
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                        seg_audio.export(seg_file.name, format='wav')
                        seg_path = seg_file.name
                        temp_files.append(seg_path)
                    
                    # Transcrever segmento
                    transcription_text = self.transcribe_segment_safe(model, seg_path, retry_count=3)
                    
                    # Processar texto se válido
                    if transcription_text.strip():
                        processed_text = self.text_processor.clean_text(transcription_text)
                        
                        # Verificar novamente após limpeza
                        if processed_text.strip() and not is_invalid_transcription(processed_text):
                            timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                            speaker_name = self.text_processor.format_speaker_name(seg.speaker)
                            formatted_segments.append(f"{timestamp} {speaker_name}:\n{processed_text}")
                            valid_transcriptions += 1
                            logger.info(f"✅ Segmento {i+1} transcrito: {len(processed_text)} caracteres")
                        else:
                            logger.info(f"❌ Segmento {i+1} descartado: conteúdo inválido")
                    else:
                        logger.info(f"⚠️ Segmento {i+1} vazio")
                
                except Exception as e:
                    logger.error(f"Erro ao processar segmento {i+1}: {e}")
                    continue
            
            # Verificar se temos resultados válidos
            if not formatted_segments:
                logger.warning("Nenhum segmento foi transcrito com sucesso")
                return "Não foi possível transcrever este áudio. O áudio pode estar silencioso, com baixa qualidade ou sem fala clara."
            
            result = "\n".join(formatted_segments)  # Uma linha entre segmentos
            logger.info(f"🎉 Transcrição concluída: {valid_transcriptions}/{total_segments} segmentos válidos")
            
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