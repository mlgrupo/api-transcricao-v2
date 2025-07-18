#!/usr/bin/env python3
"""
Sistema de Transcrição Avançado com Diarização - Versão Otimizada CPU
Otimizado para 8 vCPUs e 32GB RAM sem GPU
"""
import sys
import json
import logging
import whisper
import os
import tempfile
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import re
import signal
import time
import torch
from diarization import diarize_audio, DiarizationSegment

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np

# Processamento de texto
try:
    from text_processor import TextProcessor, TextProcessingRules
except ImportError:
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

class OptimizedAudioPreprocessor:
    """Pré-processador otimizado para CPU"""
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        # Configurar para usar múltiplos cores
        mp.set_start_method('spawn', force=True)
    
    def normalize_audio(self, audio: AudioSegment) -> AudioSegment:
        """Normalização otimizada"""
        try:
            # Normalização com headroom conservador
            normalized = normalize(audio, headroom=2.0)
            return normalized
        except Exception as e:
            logger.warning(f"Erro na normalização: {e}")
            return audio
    
    def enhance_speech(self, audio: AudioSegment) -> AudioSegment:
        """Melhorar clareza da fala"""
        try:
            # Aplicar filtro passa-alta leve para remover ruído baixo
            # Filtro simples usando pydub
            if audio.rms > 0:
                # Reduzir ruído de fundo mantendo a fala
                enhanced = audio.high_pass_filter(80)  # Remove frequências abaixo de 80Hz
                enhanced = enhanced.low_pass_filter(8000)  # Remove frequências acima de 8kHz
                return enhanced
            return audio
        except Exception as e:
            logger.warning(f"Erro no enhancement: {e}")
            return audio
    
    def convert_format(self, audio: AudioSegment) -> AudioSegment:
        """Conversão de formato otimizada"""
        try:
            # Resample se necessário
            if audio.frame_rate != self.sample_rate:
                audio = audio.set_frame_rate(self.sample_rate)
            
            # Converter para mono
            if audio.channels != self.channels:
                audio = audio.set_channels(self.channels)
            
            return audio
        except Exception as e:
            logger.warning(f"Erro na conversão: {e}")
            return audio
    
    def process(self, audio: AudioSegment) -> AudioSegment:
        """Pipeline completo de pré-processamento"""
        logger.info("Iniciando pré-processamento otimizado...")
        original_duration = len(audio)
        
        # Pipeline de processamento
        audio = self.enhance_speech(audio)
        audio = self.normalize_audio(audio)
        audio = self.convert_format(audio)
        
        final_duration = len(audio)
        logger.info(f"Pré-processamento concluído: {original_duration}ms -> {final_duration}ms")
        return audio

class EnhancedTextProcessor:
    """Processador de texto melhorado"""
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
        """Limpeza avançada de texto"""
        if not text or not text.strip():
            return ""
        
        try:
            if self.text_processor:
                text = self.text_processor.process(text)
        except Exception as e:
            logger.warning(f"Erro no processamento: {e}")
        
        # Limpeza básica
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Manter apenas caracteres válidos
        text = re.sub(r'[^\w\s\.,\!\?\;\:\-\(\)\[\]\"\'áàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]', '', text)
        
        # Capitalizar início de frases
        sentences = re.split(r'([.!?]+)', text)
        for i in range(0, len(sentences), 2):
            if sentences[i].strip():
                sentences[i] = sentences[i].strip().capitalize()
        text = ''.join(sentences)
        
        return text
    
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        """Formatação precisa de timestamp"""
        def seconds_to_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
        
        start_str = seconds_to_time(start_time)
        end_str = seconds_to_time(end_time)
        return f"[{start_str} - {end_str}]"
    
    def format_speaker_name(self, speaker: str) -> str:
        """Formatar nome do locutor"""
        if speaker.startswith("SPEAKER_"):
            try:
                number = int(speaker.split("_")[1]) + 1
                return f"Locutor {number:02d}"
            except (IndexError, ValueError):
                return speaker
        return speaker

def is_valid_transcription(text: str) -> bool:
    """Validação mais rigorosa de transcrições"""
    if not text or len(text.strip()) < 3:
        return False
    
    text_lower = text.lower().strip()
    
    # Frases que indicam erro do modelo
    invalid_phrases = [
        "transcreva com a maior precisão",
        "transcreva com maior precisão",
        "este é um áudio em português",
        "agradeço a você por assistir",
        "obrigado por assistir",
        "se inscreva no canal",
        "deixe seu like",
        "compartilhe este vídeo"
    ]
    
    for phrase in invalid_phrases:
        if phrase in text_lower:
            return False
    
    # Verificar repetições excessivas
    words = text_lower.split()
    if len(words) > 2:
        word_count = {}
        for word in words:
            if len(word) > 2:
                word_count[word] = word_count.get(word, 0) + 1
        
        # Se mais de 70% das palavras são repetição da mesma palavra
        max_count = max(word_count.values()) if word_count else 0
        if max_count > len(words) * 0.7:
            return False
    
    # Verificar se não é só pontuação
    if re.match(r'^[\s\.,\!\?\;\:\-\(\)\[\]\"\']*$', text):
        return False
    
    return True

class OptimizedTranscriptionProcessor:
    """Processador de transcrição otimizado para CPU"""
    def __init__(self):
        self.audio_preprocessor = OptimizedAudioPreprocessor()
        self.text_processor = EnhancedTextProcessor()
        self.model = None
        self._setup_cpu_optimization()
    
    def _setup_cpu_optimization(self):
        """Configurar otimizações para CPU"""
        # Configurar PyTorch para CPU
        torch.set_num_threads(8)  # 8 vCPUs
        torch.set_num_interop_threads(8)
        
        # Desabilitar CUDA
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        
        # Configurar OpenMP para melhor performance
        os.environ['OMP_NUM_THREADS'] = '8'
        
        logger.info("Configurações CPU otimizadas aplicadas")
    
    def load_model(self, model_size: str = "large") -> whisper.Whisper:
        """Carregar modelo Whisper otimizado para CPU"""
        if self.model is None:
            logger.info(f"Carregando modelo Whisper {model_size} otimizado para CPU...")
            
            try:
                # Carregar modelo com configurações CPU
                self.model = whisper.load_model(
                    model_size,
                    device="cpu",
                    download_root=None,
                    in_memory=True  # Manter na memória para melhor performance
                )
                
                # Configurar modelo para CPU
                self.model.eval()  # Modo de inferência
                
                logger.info(f"Modelo {model_size} carregado com sucesso")
                
            except Exception as e:
                logger.error(f"Erro ao carregar modelo {model_size}: {e}")
                # Fallback para modelos menores
                fallback_models = ["medium", "base", "small"]
                for fallback in fallback_models:
                    try:
                        logger.info(f"Tentando modelo {fallback}...")
                        self.model = whisper.load_model(fallback, device="cpu")
                        logger.info(f"Modelo {fallback} carregado como fallback")
                        break
                    except Exception as fe:
                        logger.warning(f"Falha no modelo {fallback}: {fe}")
                        continue
                
                if self.model is None:
                    raise RuntimeError("Não foi possível carregar nenhum modelo Whisper")
        
        return self.model
    
    def transcribe_segment_optimized(self, model, seg_path: str, attempt: int = 0) -> str:
        """Transcrição otimizada com múltiplas estratégias"""
        try:
            # Timeout generoso para CPU
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(180)  # 3 minutos
            
            # Configurações baseadas na tentativa
            if attempt == 0:
                # Primeira tentativa: qualidade máxima
                result = model.transcribe(
                    seg_path,
                    language="pt",
                    task="transcribe",
                    verbose=False,
                    fp16=False,  # CPU não suporta FP16
                    temperature=0.0,
                    compression_ratio_threshold=2.2,
                    logprob_threshold=-0.8,
                    no_speech_threshold=0.3,
                    condition_on_previous_text=False,
                    initial_prompt="Esta é uma conversa natural em português brasileiro.",
                    suppress_tokens=[-1],
                    word_timestamps=True  # Para melhor precisão temporal
                )
            elif attempt == 1:
                # Segunda tentativa: mais permissivo
                result = model.transcribe(
                    seg_path,
                    language="pt",
                    task="transcribe",
                    verbose=False,
                    fp16=False,
                    temperature=0.2,
                    compression_ratio_threshold=2.8,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.2,
                    condition_on_previous_text=False,
                    initial_prompt="Conversa em português.",
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
                    temperature=0.4,
                    compression_ratio_threshold=3.5,
                    logprob_threshold=-1.2,
                    no_speech_threshold=0.1,
                    condition_on_previous_text=False,
                    suppress_tokens=[-1]
                )
            
            signal.alarm(0)
            
            transcription = result.get("text", "").strip()
            
            if is_valid_transcription(transcription):
                logger.debug(f"Transcrição válida (tentativa {attempt + 1})")
                return transcription
            else:
                logger.warning(f"Transcrição inválida (tentativa {attempt + 1}): '{transcription[:50]}...'")
                return ""
                
        except TimeoutException:
            signal.alarm(0)
            logger.warning(f"Timeout na transcrição (tentativa {attempt + 1})")
            return ""
        except Exception as e:
            signal.alarm(0)
            logger.warning(f"Erro na transcrição (tentativa {attempt + 1}): {e}")
            return ""
    
    def should_split_segment(self, segment: DiarizationSegment) -> bool:
        """Determinar se um segmento deve ser dividido"""
        duration = segment.end - segment.start
        # Dividir segmentos muito longos para melhor precisão
        return duration > 30.0  # Mais de 30 segundos
    
    def split_long_segment(self, segment: DiarizationSegment, audio: AudioSegment) -> List[DiarizationSegment]:
        """Dividir segmentos longos mantendo o mesmo locutor"""
        duration = segment.end - segment.start
        if duration <= 30.0:
            return [segment]
        
        # Dividir em chunks de até 25 segundos
        chunk_duration = 25.0
        chunks = []
        current_start = segment.start
        
        while current_start < segment.end:
            chunk_end = min(current_start + chunk_duration, segment.end)
            
            # Ajustar para não cortar no meio de uma palavra (procurar silêncio)
            if chunk_end < segment.end:
                # Procurar um ponto de silêncio nos últimos 3 segundos do chunk
                search_start = max(current_start, chunk_end - 3.0)
                search_start_ms = int(search_start * 1000)
                chunk_end_ms = int(chunk_end * 1000)
                
                chunk_audio = audio[search_start_ms:chunk_end_ms]
                if len(chunk_audio) > 0:
                    # Encontrar ponto mais silencioso
                    segment_rms = []
                    for i in range(0, len(chunk_audio), 100):  # A cada 100ms
                        segment_rms.append(chunk_audio[i:i+100].rms)
                    
                    if segment_rms:
                        min_rms_idx = segment_rms.index(min(segment_rms))
                        silence_point = search_start + (min_rms_idx * 0.1)  # 100ms = 0.1s
                        if silence_point > current_start:
                            chunk_end = silence_point
            
            chunks.append(DiarizationSegment(
                start=current_start,
                end=chunk_end,
                speaker=segment.speaker,
                confidence=segment.confidence
            ))
            
            current_start = chunk_end
        
        logger.info(f"Segmento de {duration:.1f}s dividido em {len(chunks)} partes")
        return chunks
    
    def process_segments(self, segments: List[DiarizationSegment], audio: AudioSegment) -> List[DiarizationSegment]:
        """Processar segmentos para otimizar transcrição"""
        processed = []
        
        for segment in segments:
            if self.should_split_segment(segment):
                # Dividir segmentos longos
                split_segments = self.split_long_segment(segment, audio)
                processed.extend(split_segments)
            else:
                processed.append(segment)
        
        return processed
    
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        """Transcrição principal otimizada"""
        logger.info(f"Iniciando transcrição otimizada: {audio_path}")
        temp_files = []
        
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Carregar e pré-processar áudio
            logger.info("Carregando áudio...")
            audio = AudioSegment.from_file(audio_path)
            audio_duration = len(audio) / 1000.0
            logger.info(f"Duração do áudio: {audio_duration:.1f}s")
            
            audio = self.audio_preprocessor.process(audio)
            
            # Salvar áudio processado
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                temp_path = temp_file.name
                temp_files.append(temp_path)
            
            # Diarização
            logger.info("Executando diarização...")
            try:
                diarization_segments = diarize_audio(temp_path, min_segment_duration=1.0)
                
                if diarization_segments:
                    unique_speakers = set(seg.speaker for seg in diarization_segments)
                    logger.info(f"Diarização concluída: {len(diarization_segments)} segmentos, {len(unique_speakers)} locutores")
                    logger.info(f"Locutores detectados: {sorted(list(unique_speakers))}")
                else:
                    raise Exception("Nenhum segmento detectado")
                    
            except Exception as e:
                logger.error(f"Erro na diarização: {e}")
                # Fallback: usar áudio inteiro como um locutor
                diarization_segments = [DiarizationSegment(0.0, audio_duration, "SPEAKER_00", 1.0)]
                logger.info("Usando segmento único como fallback")
            
            # Processar segmentos para otimizar transcrição
            processed_segments = self.process_segments(diarization_segments, audio)
            logger.info(f"Segmentos processados: {len(processed_segments)}")
            
            # Carregar modelo Whisper
            model = self.load_model("large")
            
            # Transcrever segmentos
            formatted_segments = []
            total_segments = len(processed_segments)
            successful_transcriptions = 0
            
            for i, seg in enumerate(processed_segments):
                logger.info(f"Transcrevendo segmento {i+1}/{total_segments} ({seg.speaker}) - {seg.end-seg.start:.1f}s")
                
                try:
                    # Extrair segmento de áudio
                    start_ms = max(0, int(seg.start * 1000))
                    end_ms = min(len(audio), int(seg.end * 1000))
                    
                    if end_ms <= start_ms or (end_ms - start_ms) < 1000:  # Menos de 1 segundo
                        logger.info(f"Segmento muito curto, pulando")
                        continue
                    
                    seg_audio = audio[start_ms:end_ms]
                    
                    # Salvar segmento temporário
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                        seg_audio.export(seg_file.name, format='wav')
                        seg_path = seg_file.name
                        temp_files.append(seg_path)
                    
                    # Tentar transcrever com múltiplas estratégias
                    transcription_text = ""
                    for attempt in range(3):
                        transcription_text = self.transcribe_segment_optimized(model, seg_path, attempt)
                        if transcription_text:
                            break
                        if attempt < 2:
                            logger.info(f"Tentativa {attempt + 1} falhou, tentando novamente...")
                    
                    if transcription_text:
                        # Processar texto
                        processed_text = self.text_processor.clean_text(transcription_text)
                        
                        if processed_text and is_valid_transcription(processed_text):
                            timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                            speaker_name = self.text_processor.format_speaker_name(seg.speaker)
                            
                            formatted_segments.append(f"{timestamp} {speaker_name}:\n{processed_text}\n")
                            successful_transcriptions += 1
                            
                            logger.info(f"✅ Segmento {i+1} transcrito: '{processed_text[:50]}{'...' if len(processed_text) > 50 else ''}'")
                        else:
                            logger.info(f"❌ Segmento {i+1} descartado após validação")
                    else:
                        logger.info(f"⚠️ Segmento {i+1} não pôde ser transcrito")
                
                except Exception as e:
                    logger.error(f"Erro ao processar segmento {i+1}: {e}")
                    continue
            
            # Compilar resultado
            if not formatted_segments:
                logger.warning("Nenhum segmento transcrito com sucesso")
                return "Não foi possível transcrever este áudio. O arquivo pode estar corrompido, sem fala clara ou com qualidade muito baixa."
            
            result = "\n".join(formatted_segments)
            
            # Estatísticas finais
            success_rate = (successful_transcriptions / total_segments) * 100
            logger.info(f"🎉 Transcrição concluída!")
            logger.info(f"   - Segmentos transcritos: {successful_transcriptions}/{total_segments} ({success_rate:.1f}%)")
            logger.info(f"   - Caracteres gerados: {len(result)}")
            
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
                    logger.warning(f"Erro ao limpar {temp_file}: {e}")

def main():
    """Função principal"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Por favor, forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Validar arquivo
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
        
        # Verificar tamanho do arquivo
        file_size = os.path.getsize(audio_path) / (1024 * 1024)  # MB
        logger.info(f"Processando arquivo: {audio_path} ({file_size:.1f}MB)")
        
        # Executar transcrição
        processor = OptimizedTranscriptionProcessor()
        result = processor.transcribe_audio(audio_path, output_dir)
        
        # Salvar resultado se solicitado
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"Resultado salvo em: {output_file}")
        
        # Retornar resultado
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "optimized_diarization_whisper",
            "timestamp": datetime.now().isoformat(),
            "file_size_mb": file_size,
            "model_used": "large"
        }
        
        print(json.dumps(output, ensure_ascii=False, indent=2))
        
    except Exception as e:
        logger.error(f"Erro na execução: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()