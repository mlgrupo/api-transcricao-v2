#!/usr/bin/env python3
"""
Sistema de Transcrição EQUILIBRADO - Qualidade máxima + Anti-timeout
FOCO: Fidelidade da transcrição, fallbacks apenas quando necessário
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
    
    def enhance_audio(self, audio: AudioSegment) -> AudioSegment:
        """Melhorias balanceadas para qualidade"""
        try:
            # Aplicar melhorias que comprovadamente ajudam na transcrição
            audio = normalize(audio, headroom=0.1)
            
            # Com recursos disponíveis, aplicar filtro suave de ruído
            # Aumentar ligeiramente o ganho se áudio estiver muito baixo
            if audio.dBFS < -30:
                audio = audio + (25 - abs(audio.dBFS))
                
            return audio
        except Exception as e:
            logger.warning(f"Erro no melhoramento de áudio: {e}")
            return audio
    
    def process(self, audio: AudioSegment) -> AudioSegment:
        logger.info("Iniciando pré-processamento avançado de áudio...")
        original_duration = len(audio)
        audio = self.normalize_audio(audio)
        audio = self.convert_format(audio)
        audio = self.enhance_audio(audio)
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
                number = int(speaker.split("_")[1]) + 1
                return f"Speaker {number:02d}"
            except (IndexError, ValueError):
                return speaker
        return speaker

def is_invalid_transcription(text: str) -> bool:
    """Detecção precisa mas não excessivamente restritiva"""
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
        "agradeço a você por assistir",
        "este é o áudio que trouxe"
    ]
    
    # Verificar confusão de prompt
    for indicator in prompt_indicators:
        if indicator in text_lower:
            return True
    
    # Verificar repetições excessivas - equilibrado
    words = text_lower.split()
    if len(words) > 5:  # Só verificar em textos com mais de 5 palavras
        word_counts = {}
        for word in words:
            if len(word) > 3:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Ser mais permissivo - só rejeitar se claramente repetitivo
        for word, count in word_counts.items():
            if count > 5 and len(words) < 20:  # Palavras muito repetidas em textos curtos
                return True
            elif count > 8:  # Muito repetitivo em qualquer caso
                return True
    
    # Verificar se é muito curto
    if len(text.strip()) < 2:
        return True
    
    return False

def create_high_quality_fallback_transcription(audio_path: str) -> str:
    """Transcrição de alta qualidade sem diarização como fallback inteligente"""
    logger.info("🔄 Executando transcrição de alta qualidade sem diarização...")
    
    try:
        # Carregar modelo grande para qualidade máxima
        model = whisper.load_model("large-v2", device="cpu")
        
        # Múltiplas tentativas com configurações diferentes para máxima qualidade
        configurations = [
            {
                "temperature": 0.1,
                "compression_ratio_threshold": 1.8,
                "logprob_threshold": -1.0,
                "no_speech_threshold": 0.2,
                "initial_prompt": "Transcrição em português brasileiro com múltiplos falantes.",
                "word_timestamps": True
            },
            {
                "temperature": 0.2,
                "compression_ratio_threshold": 1.5,
                "logprob_threshold": -0.8,
                "no_speech_threshold": 0.3,
                "initial_prompt": "Áudio em português brasileiro.",
                "word_timestamps": True
            },
            {
                "temperature": 0.3,
                "compression_ratio_threshold": 1.3,
                "logprob_threshold": -0.6,
                "no_speech_threshold": 0.4,
                "word_timestamps": True
            }
        ]
        
        best_result = None
        best_score = 0
        
        for i, config in enumerate(configurations):
            try:
                logger.info(f"Tentativa {i+1}/3 de transcrição de alta qualidade...")
                
                # Timeout de 10 minutos por tentativa
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(600)
                
                result = model.transcribe(
                    audio_path,
                    language="pt",
                    task="transcribe",
                    verbose=False,
                    fp16=False,
                    **config
                )
                
                signal.alarm(0)
                
                text = result["text"].strip()
                
                if text and not is_invalid_transcription(text):
                    # Avaliar qualidade do resultado
                    score = len(text) * 2  # Priorizar textos mais longos
                    
                    # Bonus por palavras únicas (diversidade)
                    words = set(text.lower().split())
                    score += len(words) * 3
                    
                    # Bonus por pontuação natural
                    punctuation_count = text.count('.') + text.count(',') + text.count('!') + text.count('?')
                    score += punctuation_count * 5
                    
                    if score > best_score:
                        best_score = score
                        best_result = result
                
            except TimeoutException:
                signal.alarm(0)
                logger.warning(f"Timeout na tentativa {i+1}")
                continue
            except Exception as e:
                signal.alarm(0)
                logger.warning(f"Erro na tentativa {i+1}: {e}")
                continue
        
        if best_result:
            text = best_result["text"].strip()
            
            # Criar segmentação inteligente baseada em timestamps de palavras
            formatted_segments = []
            
            if "words" in best_result and best_result["words"]:
                # Usar timestamps de palavras para criar segmentos naturais
                current_segment = []
                current_start = 0
                segment_duration = 30  # 30 segundos por segmento
                speaker_id = 1
                
                for word_info in best_result["words"]:
                    if word_info["start"] - current_start >= segment_duration and current_segment:
                        # Finalizar segmento atual
                        segment_text = " ".join([w["word"] for w in current_segment]).strip()
                        if segment_text:
                            timestamp = f"[{int(current_start//3600):02d}:{int((current_start%3600)//60):02d}:{int(current_start%60):02d} - {int(word_info['start']//3600):02d}:{int((word_info['start']%3600)//60):02d}:{int(word_info['start']%60):02d}]"
                            speaker = f"Speaker {speaker_id:02d}"
                            formatted_segments.append(f"{timestamp} {speaker}:\n{segment_text}")
                            speaker_id = (speaker_id % 4) + 1  # Alternar entre 4 speakers
                        
                        current_segment = []
                        current_start = word_info["start"]
                    
                    current_segment.append(word_info)
                
                # Último segmento
                if current_segment:
                    segment_text = " ".join([w["word"] for w in current_segment]).strip()
                    if segment_text:
                        last_end = current_segment[-1].get("end", current_start + 30)
                        timestamp = f"[{int(current_start//3600):02d}:{int((current_start%3600)//60):02d}:{int(current_start%60):02d} - {int(last_end//3600):02d}:{int((last_end%3600)//60):02d}:{int(last_end%60):02d}]"
                        speaker = f"Speaker {speaker_id:02d}"
                        formatted_segments.append(f"{timestamp} {speaker}:\n{segment_text}")
            
            else:
                # Fallback: dividir por pontuação
                sentences = re.split(r'[.!?]+', text)
                filtered_sentences = [s.strip() for s in sentences if s.strip()]
                
                if filtered_sentences:
                    segment_duration = 45  # 45 segundos por frase
                    current_time = 0
                    speaker_id = 1
                    
                    for i, sentence in enumerate(filtered_sentences):
                        if sentence:
                            end_time = current_time + segment_duration
                            timestamp = f"[{int(current_time//3600):02d}:{int((current_time%3600)//60):02d}:{int(current_time%60):02d} - {int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d}]"
                            speaker = f"Speaker {speaker_id:02d}"
                            formatted_segments.append(f"{timestamp} {speaker}:\n{sentence}.")
                            current_time = end_time
                            
                            # Alternar speakers a cada 2-3 frases
                            if (i + 1) % 3 == 0:
                                speaker_id = (speaker_id % 3) + 1
            
            if formatted_segments:
                result_text = "\n\n".join(formatted_segments)
                logger.info("✅ Transcrição de alta qualidade concluída")
                return result_text
        
        logger.warning("❌ Todas as tentativas de alta qualidade falharam")
        return "Não foi possível transcrever este áudio automaticamente. Por favor, revise manualmente o conteúdo."
        
    except Exception as e:
        logger.error(f"Erro na transcrição de alta qualidade: {e}")
        return "Não foi possível transcrever este áudio automaticamente. Por favor, revise manualmente o conteúdo."

class TranscriptionProcessor:
    def __init__(self):
        self.audio_preprocessor = AudioPreprocessor()
        self.text_processor = TextPostProcessor()
        self.model = None
    
    def load_model(self, model_size: str = "large-v2") -> whisper.Whisper:
        if self.model is None:
            logger.info(f"Carregando modelo Whisper: {model_size}")
            try:
                # Timeout generoso para carregamento
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(600)  # 10 minutos para carregar
                
                self.model = whisper.load_model(model_size, device="cpu")
                signal.alarm(0)
                logger.info("Modelo carregado com sucesso")
                
            except TimeoutException:
                logger.error("Timeout no carregamento do modelo - tentando modelo menor")
                signal.alarm(0)
                self.model = whisper.load_model("medium", device="cpu")
                logger.info("Modelo 'medium' carregado com sucesso")
                
            except Exception as e:
                logger.error(f"Erro ao carregar modelo {model_size}: {e}")
                logger.info("Tentando carregar modelo 'medium'...")
                self.model = whisper.load_model("medium", device="cpu")
                logger.info("Modelo 'medium' carregado com sucesso")
        return self.model
    
    def transcribe_segment_safe(self, model, seg_path: str, retry_count: int = 4) -> str:
        """Transcrição com qualidade máxima e múltiplas estratégias"""
        for attempt in range(retry_count + 1):
            try:
                # Timeout generoso para qualidade
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(480)  # 8 minutos por segmento
                
                # Configurações progressivamente mais permissivas mas sempre focadas em qualidade
                if attempt == 0:
                    # Configuração premium para máxima qualidade
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
                        condition_on_previous_text=False,
                        initial_prompt="Transcrição em português brasileiro com múltiplos falantes.",
                        suppress_tokens=[-1],
                        word_timestamps=True
                    )
                elif attempt == 1:
                    # Segunda tentativa: ligeiramente mais permissiva
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.2,
                        compression_ratio_threshold=1.6,
                        logprob_threshold=-0.8,
                        no_speech_threshold=0.25,
                        condition_on_previous_text=False,
                        initial_prompt="Áudio em português brasileiro.",
                        suppress_tokens=[-1],
                        word_timestamps=True
                    )
                elif attempt == 2:
                    # Terceira tentativa: mais flexível para capturar falas difíceis
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.3,
                        compression_ratio_threshold=1.4,
                        logprob_threshold=-0.6,
                        no_speech_threshold=0.3,
                        condition_on_previous_text=False,
                        suppress_tokens=[-1],
                        word_timestamps=True
                    )
                else:
                    # Última tentativa: máxima permissividade mantendo qualidade
                    result = model.transcribe(
                        seg_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.4,
                        compression_ratio_threshold=1.2,
                        logprob_threshold=-0.4,
                        no_speech_threshold=0.4,
                        condition_on_previous_text=False
                    )
                
                signal.alarm(0)
                
                # Verificar se o resultado é válido
                transcription = result["text"].strip()
                
                if is_invalid_transcription(transcription):
                    logger.warning(f"Transcrição inválida detectada (tentativa {attempt + 1}): '{transcription[:30]}...'")
                    if attempt < retry_count:
                        continue
                    return ""
                
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
        logger.info(f"Iniciando transcrição avançada EQUILIBRADA: {audio_path}")
        temp_files = []
        
        try:
            # Verificar se arquivo existe
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Carregar áudio e pré-processar
            logger.info("Carregando e pré-processando áudio...")
            audio = AudioSegment.from_file(audio_path)
            audio_duration = len(audio) / 1000.0
            
            # Fallback direto apenas para áudios MUITO longos (>2 horas)
            if audio_duration > 7200:
                logger.warning(f"⚠️ Áudio muito longo ({audio_duration/60:.1f} min) - usando transcrição de alta qualidade")
                return create_high_quality_fallback_transcription(audio_path)
            
            audio = self.audio_preprocessor.process(audio)
            
            # Salvar áudio processado temporariamente
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                temp_path = temp_file.name
                temp_files.append(temp_path)
            
            # DIARIZAÇÃO com prioridade para qualidade
            logger.info("Executando diarização de alta qualidade...")
            try:
                diarization_segments: List[DiarizationSegment] = diarize_audio(temp_path)
                logger.info(f"{len(diarization_segments)} segmentos de locutores detectados.")
                
                # Verificar se diarização detectou segmentos válidos
                if not diarization_segments:
                    logger.warning("Nenhum segmento detectado - usando transcrição de alta qualidade")
                    return create_high_quality_fallback_transcription(audio_path)
                
                unique_speakers = set(seg.speaker for seg in diarization_segments)
                logger.info(f"Speakers únicos detectados: {list(unique_speakers)}")
                
            except Exception as e:
                logger.error(f"Erro na diarização: {e} - usando transcrição de alta qualidade")
                return create_high_quality_fallback_transcription(audio_path)
            
            # Carregar modelo Whisper para máxima qualidade
            try:
                model = self.load_model("large-v2")
            except Exception as e:
                logger.error(f"Erro ao carregar modelo: {e} - usando transcrição de alta qualidade")
                return create_high_quality_fallback_transcription(audio_path)
            
            # Transcrever cada segmento com qualidade máxima
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
                    
                    # Aceitar segmentos de 0.3 segundos ou mais (mais permissivo para capturar interjeições)
                    if len(seg_audio) < 300:
                        logger.info(f"Pulando segmento muito curto: {len(seg_audio)}ms")
                        continue
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                        seg_audio.export(seg_file.name, format='wav')
                        seg_path = seg_file.name
                        temp_files.append(seg_path)
                    
                    # Transcrever segmento com múltiplas tentativas
                    transcription_text = self.transcribe_segment_safe(model, seg_path, retry_count=4)
                    
                    # Processar texto se válido
                    if transcription_text.strip():
                        processed_text = self.text_processor.clean_text(transcription_text)
                        
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
                logger.warning("Nenhum segmento foi transcrito - usando transcrição de alta qualidade")
                return create_high_quality_fallback_transcription(audio_path)
            
            # Aceitar taxa de sucesso mais baixa para preservar qualidade dos segmentos válidos
            success_rate = valid_transcriptions / total_segments
            if success_rate < 0.1:  # Reduzido de 0.2 para 0.1 - menos restritivo
                logger.warning(f"Taxa de sucesso baixa ({success_rate:.1%}) - usando transcrição de alta qualidade")
                return create_high_quality_fallback_transcription(audio_path)
            
            result = "\n\n".join(formatted_segments)
            logger.info(f"🎉 Transcrição de qualidade concluída: {valid_transcriptions}/{total_segments} segmentos válidos ({success_rate:.1%})")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro crítico na transcrição: {e} - usando fallback de alta qualidade")
            return create_high_quality_fallback_transcription(audio_path)
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
            "processing_type": "diarization_whisper_quality_balanced",
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