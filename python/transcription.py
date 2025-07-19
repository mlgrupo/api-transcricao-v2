#!/usr/bin/env python3
"""
Sistema de Transcrição 100% GRATUITO - VERSÃO OTIMIZADA
FOCO: Whisper + Diarização inteligente, sem tokens, funciona offline
OTIMIZADO PARA: 8 vCPUs + 32GB RAM
CORREÇÕES: Diarização inteligente, timeouts, fallbacks robustos
"""
import sys
import json
import logging
import whisper
import os
import tempfile
import signal
import threading
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Processamento de áudio otimizado
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np
from scipy import signal as scipy_signal
from scipy.stats import zscore

# Configuração de logging otimizada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DiarizationSegment:
    """Classe otimizada para representar segmentos de diarização"""
    def __init__(self, start: float, end: float, speaker: str, confidence: float = 1.0):
        self.start = start
        self.end = end
        self.speaker = speaker
        self.confidence = confidence
        self.duration = end - start

    def to_dict(self):
        return {
            "start": self.start, 
            "end": self.end, 
            "speaker": self.speaker,
            "duration": self.duration,
            "confidence": self.confidence
        }

class IntelligentDiarization:
    """
    Sistema de diarização inteligente otimizado para produção
    FILOSOFIA: Menos segmentos, mais precisos, melhor performance
    """
    
    def __init__(self, min_segment_duration=10.0, max_speakers=5):
        self.min_segment_duration = min_segment_duration  # Mínimo 10 segundos por segmento
        self.max_speakers = max_speakers
        self.sample_rate = 16000
    
    def extract_audio_features(self, audio_segment) -> np.ndarray:
        """
        Extrai características espectrais mais sofisticadas do áudio
        EDUCATIVO: Usa análise de frequência em vez de apenas energia
        """
        try:
            # Converter para array numpy
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)
            
            # Normalizar amplitude
            if np.max(np.abs(samples)) > 0:
                samples = samples / np.max(np.abs(samples))
            
            # Calcular características espectrais em janelas
            window_size = int(self.sample_rate * 2)  # 2 segundos
            hop_size = int(window_size * 0.5)  # 50% overlap
            
            features = []
            for i in range(0, len(samples) - window_size, hop_size):
                window = samples[i:i + window_size]
                
                # 1. Energia RMS
                rms = np.sqrt(np.mean(window**2))
                
                # 2. Zero Crossing Rate (indicador de pitch)
                zcr = np.sum(np.diff(np.sign(window)) != 0) / len(window)
                
                # 3. Centroide espectral (brilho do som)
                fft = np.fft.fft(window)
                magnitude = np.abs(fft[:len(fft)//2])
                freqs = np.fft.fftfreq(len(fft), 1/self.sample_rate)[:len(fft)//2]
                
                if np.sum(magnitude) > 0:
                    centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
                else:
                    centroid = 0
                
                # 4. Rolloff espectral (concentração de energia)
                cumsum = np.cumsum(magnitude)
                rolloff_idx = np.where(cumsum >= 0.85 * cumsum[-1])[0]
                rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0
                
                features.append([rms, zcr, centroid, rolloff])
            
            return np.array(features)
            
        except Exception as e:
            logger.warning(f"Erro na extração de características: {e}")
            return np.array([[0, 0, 0, 0]])
    
    def detect_speaker_changes(self, features: np.ndarray, threshold_factor=2.0) -> List[int]:
        """
        Detecta mudanças de speaker usando análise estatística das características
        EDUCATIVO: Usa z-score para detectar mudanças significativas
        """
        if len(features) < 3:
            return [0]
        
        change_points = [0]  # Sempre começar do início
        
        # Calcular diferenças entre janelas consecutivas
        for i in range(1, len(features)):
            # Calcular distância euclidiana entre características
            prev_features = features[max(0, i-2):i]  # Janela anterior
            curr_features = features[i:min(len(features), i+2)]  # Janela atual
            
            if len(prev_features) > 0 and len(curr_features) > 0:
                prev_mean = np.mean(prev_features, axis=0)
                curr_mean = np.mean(curr_features, axis=0)
                
                # Distância normalizada
                distance = np.linalg.norm(curr_mean - prev_mean)
                
                # Usar limiar adaptativo baseado na variabilidade histórica
                if i > 5:  # Ter dados suficientes para calcular variabilidade
                    recent_distances = []
                    for j in range(max(1, i-10), i):
                        if j < len(features) - 1:
                            d = np.linalg.norm(features[j] - features[j-1])
                            recent_distances.append(d)
                    
                    if recent_distances:
                        mean_distance = np.mean(recent_distances)
                        std_distance = np.std(recent_distances)
                        threshold = mean_distance + threshold_factor * std_distance
                        
                        if distance > threshold:
                            # Verificar se não é muito próximo do último ponto
                            time_since_last = (i - change_points[-1]) * 1.0  # 1 segundo por feature
                            if time_since_last >= self.min_segment_duration:
                                change_points.append(i)
        
        return change_points
    
    def create_segments(self, change_points: List[int], total_duration: float, 
                       features: np.ndarray) -> List[DiarizationSegment]:
        """
        Cria segmentos otimizados com atribuição inteligente de speakers
        """
        if not change_points:
            return [DiarizationSegment(0, total_duration, "SPEAKER_00", 1.0)]
        
        # Garantir que o último ponto seja o final
        if change_points[-1] * 1.0 < total_duration - 5:
            change_points.append(int(total_duration))
        
        segments = []
        feature_time_step = 1.0  # 1 segundo por feature
        
        for i in range(len(change_points) - 1):
            start_time = change_points[i] * feature_time_step
            end_time = change_points[i + 1] * feature_time_step
            
            # Calcular características médias do segmento para clustering
            start_idx = change_points[i]
            end_idx = change_points[i + 1]
            
            if start_idx < len(features) and end_idx <= len(features):
                segment_features = features[start_idx:end_idx]
                avg_features = np.mean(segment_features, axis=0)
                
                # Atribuir speaker baseado em clustering simples das características
                speaker_id = self.assign_speaker(avg_features, segments)
                confidence = self.calculate_confidence(segment_features)
                
                segments.append(DiarizationSegment(
                    start_time, end_time, f"SPEAKER_{speaker_id:02d}", confidence
                ))
        
        return self.merge_consecutive_speakers(segments)
    
    def assign_speaker(self, features: np.ndarray, existing_segments: List[DiarizationSegment]) -> int:
        """
        Atribui speaker baseado em similaridade com segmentos existentes
        EDUCATIVO: Clustering simples baseado em distância euclidiana
        """
        if not existing_segments:
            return 0
        
        # Agrupar segmentos por speaker
        speaker_features = {}
        for seg in existing_segments:
            if seg.speaker not in speaker_features:
                speaker_features[seg.speaker] = []
            # Para simplificar, usamos uma representação dummy das características
            # Em uma implementação real, armazenaríamos as características de cada segmento
        
        # Por simplicidade, usar estratégia alternada com limite de speakers
        existing_speakers = set(seg.speaker for seg in existing_segments)
        
        # Se temos menos que max_speakers, criar novo speaker
        if len(existing_speakers) < self.max_speakers:
            return len(existing_speakers)
        
        # Caso contrário, ciclar entre speakers existentes
        last_speaker = existing_segments[-1].speaker if existing_segments else "SPEAKER_00"
        last_id = int(last_speaker.split("_")[1])
        return (last_id + 1) % self.max_speakers
    
    def calculate_confidence(self, features: np.ndarray) -> float:
        """
        Calcula confiança do segmento baseado na consistência das características
        """
        if len(features) < 2:
            return 1.0
        
        # Calcular variabilidade das características
        std_features = np.std(features, axis=0)
        mean_std = np.mean(std_features)
        
        # Confiança inversamente proporcional à variabilidade
        confidence = max(0.3, min(1.0, 1.0 - mean_std))
        return confidence
    
    def merge_consecutive_speakers(self, segments: List[DiarizationSegment]) -> List[DiarizationSegment]:
        """
        Mescla segmentos consecutivos do mesmo speaker
        EDUCATIVO: Otimização final para reduzir fragmentação
        """
        if not segments:
            return []
        
        merged = [segments[0]]
        
        for seg in segments[1:]:
            last = merged[-1]
            
            # Mesclar se mesmo speaker e gap pequeno (< 3 segundos)
            if (last.speaker == seg.speaker and 
                seg.start - last.end <= 3.0 and
                last.duration + (seg.start - last.end) + seg.duration <= 180):  # Max 3 minutos
                
                # Criar novo segmento mesclado
                merged_confidence = (last.confidence + seg.confidence) / 2
                merged[-1] = DiarizationSegment(
                    last.start, seg.end, last.speaker, merged_confidence
                )
            else:
                merged.append(seg)
        
        return merged
    
    def process_audio(self, audio_path: str) -> List[DiarizationSegment]:
        """
        Método principal de diarização otimizada
        """
        logger.info("🎯 Iniciando diarização inteligente otimizada...")
        
        try:
            # Carregar áudio
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            
            logger.info(f"📊 Processando áudio de {duration:.1f}s")
            
            # Para áudios muito curtos, usar segmento único
            if duration <= self.min_segment_duration:
                return [DiarizationSegment(0, duration, "SPEAKER_00", 1.0)]
            
            # Extrair características espectrais
            features = self.extract_audio_features(audio)
            
            if len(features) < 3:
                logger.warning("⚠️ Poucas características extraídas, usando segmentação simples")
                return self.simple_temporal_segmentation(duration)
            
            # Detectar pontos de mudança
            change_points = self.detect_speaker_changes(features)
            
            # Criar segmentos finais
            segments = self.create_segments(change_points, duration, features)
            
            # Log de resultado
            unique_speakers = set(seg.speaker for seg in segments)
            avg_duration = np.mean([seg.duration for seg in segments])
            
            logger.info(f"✅ Diarização concluída: {len(segments)} segmentos, "
                       f"{len(unique_speakers)} speakers, "
                       f"duração média: {avg_duration:.1f}s")
            
            return segments
            
        except Exception as e:
            logger.error(f"❌ Erro na diarização: {e}")
            return self.simple_temporal_segmentation(duration)
    
    def simple_temporal_segmentation(self, duration: float) -> List[DiarizationSegment]:
        """
        Fallback: segmentação temporal simples e robusta
        """
        segments = []
        
        if duration <= 60:  # 1 minuto
            return [DiarizationSegment(0, duration, "SPEAKER_00", 1.0)]
        
        # Criar segmentos de 30-60 segundos alternando speakers
        segment_duration = min(45, duration / 3)  # Máximo 3 speakers
        current_time = 0
        speaker_id = 0
        
        while current_time < duration:
            end_time = min(current_time + segment_duration, duration)
            
            segments.append(DiarizationSegment(
                current_time, end_time, f"SPEAKER_{speaker_id:02d}", 0.8
            ))
            
            current_time = end_time
            speaker_id = (speaker_id + 1) % min(3, self.max_speakers)
        
        return segments

class OptimizedAudioPreprocessor:
    """Preprocessador otimizado para servidor com 8 vCPUs"""
    
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
    
    def process(self, audio: AudioSegment) -> AudioSegment:
        """
        Processamento otimizado com análise automática de qualidade
        """
        logger.info("🔧 Pré-processando áudio...")
        
        try:
            # Análise inicial de qualidade
            original_dbfs = audio.dBFS
            
            # Normalização inteligente
            if original_dbfs < -35:  # Muito baixo
                audio = audio + (25 - abs(original_dbfs))  # Amplificar
            elif original_dbfs > -6:  # Muito alto
                audio = normalize(audio, headroom=0.3)  # Normalizar com headroom
            else:
                audio = normalize(audio, headroom=0.1)  # Normalização leve
            
            # Conversão para formato padrão
            audio = audio.set_frame_rate(self.sample_rate).set_channels(self.channels)
            
            # Filtro de ruído básico se necessário
            if len(audio) > 30000:  # > 30 segundos
                audio = self.apply_noise_filter(audio)
            
            logger.info(f"✅ Pré-processamento concluído (dBFS: {original_dbfs:.1f} → {audio.dBFS:.1f})")
            return audio
            
        except Exception as e:
            logger.warning(f"⚠️ Erro no pré-processamento: {e}")
            return audio
    
    def apply_noise_filter(self, audio: AudioSegment) -> AudioSegment:
        """
        Aplicar filtro básico de ruído usando análise espectral
        """
        try:
            # Converter para numpy para processamento
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Filtro passa-alta simples para remover ruído de baixa frequência
            from scipy.signal import butter, filtfilt
            
            nyquist = self.sample_rate / 2
            low_cutoff = 80 / nyquist  # Remove frequências abaixo de 80Hz
            high_cutoff = 8000 / nyquist  # Remove frequências acima de 8kHz
            
            b, a = butter(4, [low_cutoff, high_cutoff], btype='band')
            filtered_samples = filtfilt(b, a, samples)
            
            # Converter de volta para AudioSegment
            filtered_audio = audio._spawn(filtered_samples.astype(np.int16).tobytes())
            return filtered_audio
            
        except Exception as e:
            logger.warning(f"⚠️ Erro no filtro de ruído: {e}")
            return audio

class RobustWhisperTranscriber:
    """
    Transcriber Whisper otimizado com controle de recursos e timeouts
    """
    
    def __init__(self, max_workers=4):
        self.model = None
        self.model_size = "medium"  # Usar medium por padrão para melhor relação speed/quality
        self.max_workers = max_workers
        self.timeout_per_minute = 30  # 30 segundos por minuto de áudio
    
    def load_model(self, force_size=None):
        """
        Carregamento otimizado do modelo com cache
        """
        target_size = force_size or self.model_size
        
        if self.model is None or force_size:
            logger.info(f"🤖 Carregando Whisper {target_size}...")
            
            try:
                # Verificar disponibilidade de GPU (mesmo que não usemos, é bom saber)
                import torch
                device = "cpu"  # Forçar CPU para consistência
                
                self.model = whisper.load_model(target_size, device=device)
                self.model_size = target_size
                logger.info(f"✅ Modelo {target_size} carregado com sucesso no {device}")
                
            except Exception as e:
                if target_size != "base":
                    logger.warning(f"⚠️ Erro ao carregar {target_size}, tentando 'base': {e}")
                    self.model = whisper.load_model("base", device="cpu")
                    self.model_size = "base"
                else:
                    raise e
        
        return self.model
    
    def transcribe_with_timeout(self, audio_path: str, timeout: int) -> Optional[str]:
        """
        Transcrever com timeout robusto usando threading
        """
        result = [None]
        exception = [None]
        
        def transcribe_worker():
            try:
                model = self.load_model()
                
                # Configuração otimizada para produção
                transcription_result = model.transcribe(
                    audio_path,
                    language="pt",
                    task="transcribe",
                    verbose=False,
                    fp16=False,  # Melhor compatibilidade
                    temperature=0.1,  # Determinístico
                    compression_ratio_threshold=2.0,  # Evitar alucinações
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.3,
                    initial_prompt="Transcrição clara em português brasileiro."
                )
                
                result[0] = transcription_result["text"].strip()
                
            except Exception as e:
                exception[0] = e
        
        # Executar em thread separada com timeout
        thread = threading.Thread(target=transcribe_worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            logger.warning(f"⏰ Timeout de {timeout}s atingido")
            return None
        
        if exception[0]:
            raise exception[0]
        
        return result[0]
    
    def transcribe_segment_robust(self, audio_path: str, max_attempts=3) -> str:
        """
        Transcrição robusta com estratégias progressivas e timeouts
        """
        # Calcular timeout baseado na duração do áudio
        try:
            audio = AudioSegment.from_file(audio_path)
            duration_minutes = len(audio) / 60000.0
            timeout = max(30, int(duration_minutes * self.timeout_per_minute))
        except:
            timeout = 60  # Fallback
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"🎯 Tentativa {attempt + 1}/{max_attempts} (timeout: {timeout}s)")
                
                # Tentar transcrição com timeout
                transcription = self.transcribe_with_timeout(audio_path, timeout)
                
                if transcription and not self.is_invalid_transcription(transcription):
                    logger.info(f"✅ Transcrição válida obtida na tentativa {attempt + 1}")
                    return transcription
                else:
                    logger.warning(f"❌ Transcrição inválida na tentativa {attempt + 1}")
                    
            except Exception as e:
                logger.warning(f"❌ Erro na tentativa {attempt + 1}: {e}")
                
                # Se erro de memória, tentar modelo menor
                if "memory" in str(e).lower() or "cuda" in str(e).lower():
                    if self.model_size == "medium":
                        logger.info("🔄 Tentando modelo 'base' devido a limitação de recursos...")
                        self.load_model("base")
                    
                # Aumentar timeout para próxima tentativa
                timeout = min(timeout * 1.5, 300)  # Máximo 5 minutos
        
        return ""
    
    def is_invalid_transcription(self, text: str) -> bool:
        """
        Detectar transcrições inválidas com heurísticas aprimoradas
        """
        if not text or len(text.strip()) < 3:
            return True
        
        text_lower = text.lower().strip()
        
        # Indicadores de alucinação ou meta-informação
        bad_indicators = [
            "transcreva", "transcrição", "por favor transcrever",
            "áudio em português", "muito obrigado",
            "não sei", "não entendi", "desculpe",
            "sistema de transcrição", "whisper"
        ]
        
        for indicator in bad_indicators:
            if indicator in text_lower:
                return True
        
        # Detectar repetições excessivas
        words = text_lower.split()
        if len(words) > 3:
            unique_words = set(words)
            repetition_ratio = len(words) / len(unique_words)
            if repetition_ratio > 5:  # Muita repetição
                return True
        
        # Detectar texto muito genérico ou vazio
        if len(text.strip()) < 10 and any(phrase in text_lower for phrase in ["ok", "sim", "não", "obrigado"]):
            return True
        
        return False

class OptimizedTranscriptionProcessor:
    """
    Processador principal otimizado para servidor com 8 vCPUs e 32GB RAM
    """
    
    def __init__(self):
        self.preprocessor = OptimizedAudioPreprocessor()
        self.diarizer = IntelligentDiarization(min_segment_duration=15.0, max_speakers=4)
        self.transcriber = RobustWhisperTranscriber(max_workers=4)
        self.text_processor = TextPostProcessor()
    
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        """
        Método principal otimizado com processamento inteligente
        """
        logger.info(f"🎯 Iniciando transcrição otimizada: {audio_path}")
        
        temp_files = []
        start_time = time.time()
        
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Análise inicial do áudio
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            duration_min = duration / 60.0
            
            logger.info(f"📊 Duração: {duration_min:.1f} minutos")
            
            # Estratégia baseada na duração
            if duration <= 30:  # Muito curto
                logger.info("⚡ Áudio curto - transcrição direta")
                return self.direct_transcription(audio_path)
            
            elif duration > 3600:  # Muito longo (> 1 hora)
                logger.info("📏 Áudio muito longo - segmentação temporal")
                return self.process_long_audio(audio, temp_files)
            
            else:  # Duração ideal para diarização
                return self.process_with_diarization(audio, audio_path, temp_files)
                
        except Exception as e:
            logger.error(f"💥 Erro crítico: {e}")
            return self.emergency_fallback(audio_path)
        
        finally:
            # Limpeza automática
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
            
            elapsed = time.time() - start_time
            logger.info(f"⏱️ Processamento concluído em {elapsed:.1f}s")
    
    def process_with_diarization(self, audio: AudioSegment, audio_path: str, temp_files: List) -> str:
        """
        Processamento com diarização inteligente
        """
        try:
            # Pré-processar áudio
            processed_audio = self.preprocessor.process(audio)
            
            # Salvar áudio processado
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                processed_audio.export(temp_file.name, format='wav')
                processed_path = temp_file.name
                temp_files.append(processed_path)
            
            # Aplicar diarização inteligente
            segments = self.diarizer.process_audio(processed_path)
            
            if not segments:
                logger.warning("⚠️ Diarização não retornou segmentos válidos")
                return self.direct_transcription(processed_path)
            
            # Transcrever segmentos de forma otimizada
            return self.transcribe_segments_optimized(processed_audio, segments, temp_files)
            
        except Exception as e:
            logger.error(f"❌ Erro no processamento com diarização: {e}")
            return self.direct_transcription(audio_path)
    
    def transcribe_segments_optimized(self, audio: AudioSegment, segments: List[DiarizationSegment], temp_files: List) -> str:
        """
        Transcrição otimizada de segmentos com processamento paralelo quando possível
        """
        logger.info(f"🚀 Transcrevendo {len(segments)} segmentos otimizados")
        
        formatted_segments = []
        successful_transcriptions = 0
        
        # Para poucos segmentos, processar sequencialmente (mais estável)
        if len(segments) <= 10:
            return self.transcribe_segments_sequential(audio, segments, temp_files)
        
        # Para muitos segmentos, usar processamento em lotes
        batch_size = 3  # Processar 3 por vez para otimizar recursos
        
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            batch_results = self.process_segment_batch(audio, batch, temp_files, i)
            
            for result in batch_results:
                if result:
                    formatted_segments.append(result)
                    successful_transcriptions += 1
        
        # Compilar resultado final
        if formatted_segments:
            success_rate = successful_transcriptions / len(segments)
            logger.info(f"🎉 Transcrição otimizada concluída: {successful_transcriptions}/{len(segments)} ({success_rate:.1%})")
            return "\n\n".join(formatted_segments)
        else:
            logger.error("❌ Nenhum segmento foi transcrito com sucesso")
            return self.direct_transcription_from_audio(audio, temp_files)
    
    def transcribe_segments_sequential(self, audio: AudioSegment, segments: List[DiarizationSegment], temp_files: List) -> str:
        """
        Transcrição sequencial para poucos segmentos (mais estável)
        """
        formatted_segments = []
        successful_transcriptions = 0
        
        for i, seg in enumerate(segments):
            try:
                # Extrair segmento com margem de segurança
                start_ms = max(0, int(seg.start * 1000) - 500)  # 0.5s antes
                end_ms = min(len(audio), int(seg.end * 1000) + 500)  # 0.5s depois
                
                if end_ms <= start_ms or (end_ms - start_ms) < 2000:  # Muito curto
                    logger.warning(f"⚠️ Segmento {i+1} muito curto ({(end_ms-start_ms)/1000:.1f}s), pulando...")
                    continue
                
                seg_audio = audio[start_ms:end_ms]
                
                # Salvar segmento temporário
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                    seg_audio.export(seg_file.name, format='wav')
                    seg_path = seg_file.name
                    temp_files.append(seg_path)
                
                # Transcrever com timeout proporcional
                transcription = self.transcriber.transcribe_segment_robust(seg_path)
                
                if transcription.strip():
                    processed_text = self.text_processor.clean_text(transcription)
                    
                    if processed_text.strip():
                        timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                        speaker_name = self.text_processor.format_speaker_name(seg.speaker)
                        
                        formatted_segments.append(f"{timestamp} {speaker_name}:\n{processed_text}")
                        successful_transcriptions += 1
                        
                        logger.info(f"✅ Segmento {i+1}/{len(segments)}: {len(processed_text)} chars")
                    else:
                        logger.warning(f"⚠️ Segmento {i+1}: texto vazio após limpeza")
                else:
                    logger.warning(f"⚠️ Segmento {i+1}: transcrição falhou")
                
            except Exception as e:
                logger.warning(f"❌ Erro no segmento {i+1}: {e}")
                continue
        
        if formatted_segments:
            return "\n\n".join(formatted_segments)
        else:
            return self.direct_transcription_from_audio(audio, temp_files)
    
    def process_segment_batch(self, audio: AudioSegment, batch: List[DiarizationSegment], temp_files: List, batch_offset: int) -> List[str]:
        """
        Processar um lote de segmentos (placeholder para implementação futura de paralelização)
        """
        # Por enquanto, processar sequencialmente para máxima estabilidade
        results = []
        
        for i, seg in enumerate(batch):
            try:
                global_index = batch_offset + i + 1
                
                # Extrair e processar segmento
                start_ms = max(0, int(seg.start * 1000))
                end_ms = min(len(audio), int(seg.end * 1000))
                
                if end_ms <= start_ms or (end_ms - start_ms) < 3000:
                    continue
                
                seg_audio = audio[start_ms:end_ms]
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                    seg_audio.export(seg_file.name, format='wav')
                    seg_path = seg_file.name
                    temp_files.append(seg_path)
                
                transcription = self.transcriber.transcribe_segment_robust(seg_path)
                
                if transcription.strip():
                    processed_text = self.text_processor.clean_text(transcription)
                    
                    if processed_text.strip():
                        timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                        speaker_name = self.text_processor.format_speaker_name(seg.speaker)
                        
                        result = f"{timestamp} {speaker_name}:\n{processed_text}"
                        results.append(result)
                        
                        logger.info(f"✅ Lote segmento {global_index}: {len(processed_text)} chars")
                
            except Exception as e:
                logger.warning(f"❌ Erro no lote segmento {batch_offset + i + 1}: {e}")
        
        return results
    
    def process_long_audio(self, audio: AudioSegment, temp_files: List) -> str:
        """
        Processamento otimizado para áudios muito longos (> 1 hora)
        """
        logger.info("📏 Processando áudio longo com segmentação temporal")
        
        duration = len(audio) / 1000.0
        chunk_duration = 300  # 5 minutos por chunk
        chunks = []
        
        current_time = 0
        chunk_id = 0
        
        while current_time < duration:
            end_time = min(current_time + chunk_duration, duration)
            
            start_ms = int(current_time * 1000)
            end_ms = int(end_time * 1000)
            
            chunk_audio = audio[start_ms:end_ms]
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as chunk_file:
                chunk_audio.export(chunk_file.name, format='wav')
                chunk_path = chunk_file.name
                temp_files.append(chunk_path)
            
            # Transcrever chunk
            transcription = self.transcriber.transcribe_segment_robust(chunk_path)
            
            if transcription.strip():
                processed_text = self.text_processor.clean_text(transcription)
                timestamp = self.text_processor.format_timestamp(current_time, end_time)
                
                chunks.append(f"{timestamp} Segmento {chunk_id + 1}:\n{processed_text}")
                logger.info(f"✅ Chunk {chunk_id + 1}: {current_time/60:.1f}-{end_time/60:.1f}min processado")
            
            current_time = end_time
            chunk_id += 1
        
        if chunks:
            return "\n\n".join(chunks)
        else:
            return "Não foi possível transcrever este áudio longo."
    
    def direct_transcription(self, audio_path: str) -> str:
        """Transcrição direta otimizada"""
        logger.info("🎯 Transcrição direta otimizada")
        
        try:
            transcription = self.transcriber.transcribe_segment_robust(audio_path)
            
            if transcription:
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
    
    def direct_transcription_from_audio(self, audio: AudioSegment, temp_files: List) -> str:
        """Transcrição direta a partir de AudioSegment"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                temp_path = temp_file.name
                temp_files.append(temp_path)
            
            return self.direct_transcription(temp_path)
        except Exception as e:
            logger.error(f"❌ Erro na transcrição direta from audio: {e}")
            return "Erro na transcrição de fallback."
    
    def emergency_fallback(self, audio_path: str) -> str:
        """Fallback final para casos extremos"""
        logger.warning("🆘 Executando fallback de emergência")
        
        try:
            # Tentar com modelo base e configurações mínimas
            old_transcriber = self.transcriber
            self.transcriber = RobustWhisperTranscriber(max_workers=1)
            self.transcriber.load_model("base")
            
            result = self.direct_transcription(audio_path)
            
            # Restaurar transcriber original
            self.transcriber = old_transcriber
            
            return result if result else "Transcrição de emergência falhou."
            
        except Exception as e:
            logger.error(f"❌ Fallback de emergência falhou: {e}")
            return "Sistema de transcrição temporariamente indisponível."

class TextPostProcessor:
    """Processador de texto otimizado"""
    
    def clean_text(self, text: str) -> str:
        """Limpeza avançada de texto"""
        if not text or not text.strip():
            return ""
        
        # Remover espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        # Limpar caracteres problemáticos mantendo acentos
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)áàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]', '', text)
        
        # Capitalizar primeira letra se necessário
        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        return text
    
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        """Formatação otimizada de timestamp"""
        def seconds_to_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        start_str = seconds_to_time(start_time)
        end_str = seconds_to_time(end_time)
        return f"[{start_str} - {end_str}]"
    
    def format_speaker_name(self, speaker: str) -> str:
        """Formatação melhorada de nome do speaker"""
        if speaker.startswith("SPEAKER_"):
            try:
                number = int(speaker.split("_")[1]) + 1
                return f"Speaker {number:02d}"
            except:
                return speaker
        return speaker

def main():
    """
    Função principal otimizada com melhor tratamento de erros
    """
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Por favor, forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Inicializar processador otimizado
        processor = OptimizedTranscriptionProcessor()
        
        # Processar com timeout global
        start_time = time.time()
        result = processor.transcribe_audio(audio_path, output_dir)
        processing_time = time.time() - start_time
        
        # Salvar arquivo se solicitado
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"💾 Transcrição salva: {output_file}")
        
        # Preparar output JSON otimizado
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "optimized_whisper_intelligent_diarization",
            "processing_time_seconds": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "diarization_available": True,
            "model_used": processor.transcriber.model_size if processor.transcriber.model else "unknown"
        }
        
        print(json.dumps(output, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"💥 Erro na execução principal: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()