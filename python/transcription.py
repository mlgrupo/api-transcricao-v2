#!/usr/bin/env python3
"""
SISTEMA DE TRANSCRIÇÃO SIMPLES E EFICAZ
======================================
FOCO: Qualidade ao invés de complexidade
ESTRATÉGIA: Menos fallbacks, mais precisão
"""

import sys
import json
import logging
import os
import tempfile
import time
import numpy as np
import warnings
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
import re
import asyncio

# Suprimir warnings
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Imports essenciais
from pydub import AudioSegment
import librosa
import soundfile as sf

# Machine Learning
import torch
from sklearn.cluster import SpectralClustering, AgglomerativeClustering
from sklearn.metrics import silhouette_score

# Core - APENAS o que funciona de verdade
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

try:
    import whisper
    OPENAI_WHISPER_AVAILABLE = True
except ImportError:
    OPENAI_WHISPER_AVAILABLE = False

# Configuração simples
torch.set_num_threads(4)
os.environ['OMP_NUM_THREADS'] = '4'

def setup_simple_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_simple_logging()

class SimpleWhisperTranscriber:
    """
    Transcritor simples mas eficaz
    FOCO: Precisão sem repetições
    """
    
    def __init__(self):
        self.model = None
        self.model_type = None
        
    def load_model(self):
        """Carrega o melhor modelo disponível"""
        if self.model is not None:
            return self.model
            
        # Tentar Faster-Whisper primeiro
        if FASTER_WHISPER_AVAILABLE:
            try:
                logger.info("🚀 Carregando Faster-Whisper")
                self.model = WhisperModel(
                    "medium",  # Modelo médio - bom equilíbrio
                    device="cpu",
                    compute_type="int8"
                )
                self.model_type = "faster-whisper"
                logger.info("✅ Faster-Whisper carregado")
                return self.model
            except Exception as e:
                logger.warning(f"⚠️ Faster-Whisper falhou: {e}")
        
        # Fallback para OpenAI Whisper
        if OPENAI_WHISPER_AVAILABLE:
            try:
                logger.info("🚀 Carregando OpenAI Whisper")
                self.model = whisper.load_model("medium")
                self.model_type = "openai-whisper"
                logger.info("✅ OpenAI Whisper carregado")
                return self.model
            except Exception as e:
                logger.warning(f"⚠️ OpenAI Whisper falhou: {e}")
        
        raise Exception("Nenhum modelo Whisper disponível")
    
    def transcribe_full(self, audio_path: str) -> str:
        """Transcrição completa do áudio"""
        model = self.load_model()
        
        if self.model_type == "faster-whisper":
            return self._transcribe_faster_whisper(audio_path)
        elif self.model_type == "openai-whisper":
            return self._transcribe_openai_whisper(audio_path)
        else:
            raise Exception("Modelo não configurado")
    
    def _transcribe_faster_whisper(self, audio_path: str) -> str:
        """Transcrição com Faster-Whisper otimizada"""
        try:
            segments, info = self.model.transcribe(
                audio_path,
                language="pt",
                task="transcribe",
                vad_filter=False,  # DESLIGAR VAD - causa repetições
                temperature=0.0,
                compression_ratio_threshold=2.4,  # Evitar repetições
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=False,  # CRÍTICO - evita repetições
                initial_prompt="Reunião de trabalho em português:"
            )
            
            # Combinar segmentos sem duplicação
            texts = []
            last_text = ""
            
            for segment in segments:
                text = segment.text.strip()
                
                # Evitar repetições
                if text and text != last_text:
                    # Verificar sobreposição significativa
                    if not self._has_significant_overlap(text, last_text):
                        texts.append(text)
                        last_text = text
            
            return " ".join(texts)
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição Faster-Whisper: {e}")
            raise e
    
    def _transcribe_openai_whisper(self, audio_path: str) -> str:
        """Transcrição com OpenAI Whisper otimizada"""
        try:
            result = self.model.transcribe(
                audio_path,
                language="pt",
                task="transcribe",
                temperature=0.0,
                condition_on_previous_text=False,
                initial_prompt="Reunião de trabalho em português:"
            )
            
            return result["text"].strip()
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição OpenAI Whisper: {e}")
            raise e
    
    def _has_significant_overlap(self, text1: str, text2: str) -> bool:
        """Verifica se dois textos têm sobreposição significativa"""
        if not text1 or not text2:
            return False
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if len(words1) == 0 or len(words2) == 0:
            return False
        
        overlap = len(words1.intersection(words2))
        min_length = min(len(words1), len(words2))
        
        # Se mais de 70% das palavras são iguais, considerar repetição
        return overlap / min_length > 0.7

class SimpleSpeakerDiarization:
    """
    Diarização simples baseada em características espectrais
    FOCO: Detectar mais speakers corretamente
    """
    
    def __init__(self, max_speakers=6):
        self.max_speakers = max_speakers
        
    def detect_speakers(self, audio_path: str) -> List[Dict]:
        """
        Detecta speakers usando características espectrais simples
        RETORNA: Lista de segmentos com speaker_id
        """
        logger.info("🎭 Iniciando diarização de speakers")
        
        try:
            # Carregar áudio
            audio, sr = librosa.load(audio_path, sr=16000)
            
            # Criar segmentos de análise (janelas de 2 segundos)
            window_duration = 2.0
            hop_duration = 1.0
            
            window_samples = int(window_duration * sr)
            hop_samples = int(hop_duration * sr)
            
            segments = []
            features = []
            
            for i in range(0, len(audio) - window_samples, hop_samples):
                start_time = i / sr
                end_time = (i + window_samples) / sr
                
                window = audio[i:i + window_samples]
                
                # Extrair características espectrais
                if np.max(np.abs(window)) > 0.01:  # Apenas janelas com áudio
                    mfccs = librosa.feature.mfcc(y=window, sr=sr, n_mfcc=13)
                    mfcc_mean = np.mean(mfccs, axis=1)
                    
                    # Características de pitch
                    pitches, magnitudes = librosa.piptrack(y=window, sr=sr)
                    pitch_mean = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0
                    
                    # Características espectrais
                    spectral_centroid = librosa.feature.spectral_centroid(y=window, sr=sr)
                    spectral_rolloff = librosa.feature.spectral_rolloff(y=window, sr=sr)
                    
                    feature_vector = np.concatenate([
                        mfcc_mean,
                        [pitch_mean],
                        [np.mean(spectral_centroid)],
                        [np.mean(spectral_rolloff)]
                    ])
                    
                    segments.append({
                        'start': start_time,
                        'end': end_time,
                        'duration': window_duration
                    })
                    features.append(feature_vector)
            
            if len(features) < 2:
                logger.warning("⚠️ Poucos segmentos para diarização")
                return [{
                    'start': 0,
                    'end': len(audio) / sr,
                    'speaker_id': 0,
                    'speaker': 'SPEAKER_01'
                }]
            
            # Clustering para identificar speakers
            features_array = np.array(features)
            speaker_labels = self._cluster_speakers(features_array)
            
            # Combinar segmentos com labels
            speaker_segments = []
            for segment, label in zip(segments, speaker_labels):
                segment['speaker_id'] = int(label)
                segment['speaker'] = f"SPEAKER_{int(label) + 1:02d}"
                speaker_segments.append(segment)
            
            # Consolidar segmentos consecutivos do mesmo speaker
            consolidated = self._consolidate_segments(speaker_segments)
            
            n_speakers = len(set(s['speaker_id'] for s in consolidated))
            logger.info(f"🎭 {n_speakers} speakers detectados")
            
            return consolidated
            
        except Exception as e:
            logger.error(f"❌ Erro na diarização: {e}")
            # Fallback simples
            duration = self._get_duration(audio_path)
            return [{
                'start': 0,
                'end': duration,
                'speaker_id': 0,
                'speaker': 'SPEAKER_01'
            }]
    
    def _cluster_speakers(self, features: np.ndarray) -> np.ndarray:
        """Clustering de speakers usando múltiplos algoritmos"""
        best_labels = None
        best_score = -1
        best_n_speakers = 2
        
        # Normalizar features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        # Testar diferentes números de speakers
        for n_speakers in range(2, min(self.max_speakers + 1, len(features) // 2)):
            
            # Algoritmo 1: Spectral Clustering
            try:
                clusterer = SpectralClustering(
                    n_clusters=n_speakers,
                    random_state=42,
                    affinity='rbf',
                    gamma=1.0
                )
                labels = clusterer.fit_predict(features_scaled)
                
                if len(np.unique(labels)) == n_speakers:
                    score = silhouette_score(features_scaled, labels)
                    
                    if score > best_score:
                        best_score = score
                        best_labels = labels
                        best_n_speakers = n_speakers
                        
            except Exception as e:
                logger.warning(f"⚠️ Spectral clustering falhou para {n_speakers} speakers: {e}")
            
            # Algoritmo 2: Agglomerative Clustering
            try:
                clusterer = AgglomerativeClustering(
                    n_clusters=n_speakers,
                    linkage='ward'
                )
                labels = clusterer.fit_predict(features_scaled)
                
                if len(np.unique(labels)) == n_speakers:
                    score = silhouette_score(features_scaled, labels)
                    
                    if score > best_score:
                        best_score = score
                        best_labels = labels
                        best_n_speakers = n_speakers
                        
            except Exception as e:
                logger.warning(f"⚠️ Agglomerative clustering falhou para {n_speakers} speakers: {e}")
        
        if best_labels is not None:
            logger.info(f"📊 Melhor clustering: {best_n_speakers} speakers (score: {best_score:.3f})")
            return best_labels
        else:
            # Fallback: 2 speakers alternados
            logger.warning("⚠️ Clustering falhou, usando 2 speakers alternados")
            return np.array([i % 2 for i in range(len(features))])
    
    def _consolidate_segments(self, segments: List[Dict]) -> List[Dict]:
        """Consolida segmentos consecutivos do mesmo speaker"""
        if not segments:
            return segments
        
        consolidated = []
        current_segment = segments[0].copy()
        
        for next_segment in segments[1:]:
            # Se mesmo speaker e gap pequeno (< 3 segundos)
            if (next_segment['speaker_id'] == current_segment['speaker_id'] and
                next_segment['start'] - current_segment['end'] < 3.0):
                # Estender segmento atual
                current_segment['end'] = next_segment['end']
                current_segment['duration'] = current_segment['end'] - current_segment['start']
            else:
                # Salvar segmento atual e começar novo
                if current_segment['duration'] >= 1.0:  # Mínimo 1 segundo
                    consolidated.append(current_segment)
                current_segment = next_segment.copy()
        
        # Adicionar último segmento
        if current_segment['duration'] >= 1.0:
            consolidated.append(current_segment)
        
        return consolidated
    
    def _get_duration(self, audio_path: str) -> float:
        """Obter duração do áudio"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except:
            return 0.0

class SmartTranscriptionPipeline:
    """
    Pipeline inteligente mas simples
    FOCO: Qualidade e precisão
    """
    
    def __init__(self):
        self.transcriber = SimpleWhisperTranscriber()
        self.diarizer = SimpleSpeakerDiarization()
        
    async def process_audio(self, audio_path: str) -> str:
        """Pipeline completa otimizada"""
        logger.info(f"🎯 Processando: {audio_path}")
        start_time = time.time()
        
        try:
            # Verificar arquivo
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Análise de duração
            duration = self._get_audio_duration(audio_path)
            logger.info(f"⏱️ Duração: {duration:.1f}s ({duration/60:.1f}min)")
            
            # Decidir estratégia baseada na duração
            if duration < 20:
                # Áudio muito curto - apenas transcrição
                logger.info("⚡ Áudio curto - apenas transcrição")
                text = self.transcriber.transcribe_full(audio_path)
                return f"[00:00:00 - {self._format_time(duration)}] SPEAKER_01:\n{self._clean_text(text)}"
            
            elif duration < 120:
                # Áudio médio - diarização simples
                logger.info("🎭 Áudio médio - diarização simples")
                return await self._process_with_simple_diarization(audio_path)
            
            else:
                # Áudio longo - diarização completa
                logger.info("🎭 Áudio longo - diarização completa")
                return await self._process_with_full_diarization(audio_path)
            
        except Exception as e:
            logger.error(f"💥 Erro no processamento: {e}")
            # Fallback final - apenas transcrição
            try:
                text = self.transcriber.transcribe_full(audio_path)
                duration = self._get_audio_duration(audio_path)
                return f"[00:00:00 - {self._format_time(duration)}] SPEAKER_01:\n{self._clean_text(text)}"
            except:
                return "Erro na transcrição do áudio."
        
        finally:
            processing_time = time.time() - start_time
            logger.info(f"⏱️ Processamento concluído em {processing_time:.1f}s")
    
    async def _process_with_simple_diarization(self, audio_path: str) -> str:
        """Processamento com diarização simples"""
        # Detectar speakers
        speaker_segments = self.diarizer.detect_speakers(audio_path)
        
        # Transcrever segmentos
        transcriptions = []
        audio, sr = librosa.load(audio_path, sr=16000)
        
        for segment in speaker_segments:
            try:
                # Extrair segmento
                start_sample = int(segment['start'] * sr)
                end_sample = int(segment['end'] * sr)
                segment_audio = audio[start_sample:end_sample]
                
                # Salvar temporariamente
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_file:
                    sf.write(temp_file.name, segment_audio, sr)
                    
                    # Transcrever
                    text = self.transcriber.transcribe_full(temp_file.name)
                    if text and text.strip():
                        timestamp = f"[{self._format_time(segment['start'])} - {self._format_time(segment['end'])}]"
                        speaker = segment['speaker']
                        clean_text = self._clean_text(text)
                        transcriptions.append(f"{timestamp} {speaker}:\n{clean_text}")
                        
            except Exception as e:
                logger.warning(f"⚠️ Erro no segmento: {e}")
                continue
        
        return "\n\n".join(transcriptions) if transcriptions else "Erro na transcrição."
    
    async def _process_with_full_diarization(self, audio_path: str) -> str:
        """Processamento com diarização completa para áudios longos"""
        # Para áudios longos, dividir em chunks menores
        duration = self._get_audio_duration(audio_path)
        chunk_duration = 300  # 5 minutos por chunk
        
        if duration <= chunk_duration:
            return await self._process_with_simple_diarization(audio_path)
        
        # Dividir áudio em chunks
        audio = AudioSegment.from_file(audio_path)
        chunks = []
        results = []
        
        for i in range(0, len(audio), chunk_duration * 1000):
            chunk = audio[i:i + chunk_duration * 1000]
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                chunk.export(temp_file.name, format='wav')
                chunks.append({
                    'path': temp_file.name,
                    'start_time': i / 1000.0
                })
        
        # Processar cada chunk
        for chunk in chunks:
            try:
                chunk_result = await self._process_with_simple_diarization(chunk['path'])
                
                # Ajustar timestamps
                lines = chunk_result.split('\n\n')
                adjusted_lines = []
                
                for line in lines:
                    if line.strip() and '[' in line:
                        # Extrair e ajustar timestamp
                        parts = line.split('] ', 1)
                        if len(parts) == 2:
                            timestamp_part = parts[0] + ']'
                            content_part = parts[1]
                            
                            # Ajustar timestamp
                            adjusted_timestamp = self._adjust_timestamp(timestamp_part, chunk['start_time'])
                            adjusted_lines.append(f"{adjusted_timestamp} {content_part}")
                
                results.extend(adjusted_lines)
                
                # Limpar arquivo temporário
                os.unlink(chunk['path'])
                
            except Exception as e:
                logger.warning(f"⚠️ Erro no chunk: {e}")
                continue
        
        return "\n\n".join(results) if results else "Erro na transcrição."
    
    def _adjust_timestamp(self, timestamp: str, offset: float) -> str:
        """Ajusta timestamp com offset"""
        try:
            # Extrair tempos do timestamp [HH:MM:SS - HH:MM:SS]
            times = timestamp.strip('[]').split(' - ')
            start_str, end_str = times[0], times[1]
            
            start_seconds = self._time_to_seconds(start_str) + offset
            end_seconds = self._time_to_seconds(end_str) + offset
            
            return f"[{self._format_time(start_seconds)} - {self._format_time(end_seconds)}]"
        except:
            return timestamp
    
    def _time_to_seconds(self, time_str: str) -> float:
        """Converte HH:MM:SS para segundos"""
        parts = time_str.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Obter duração do áudio"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except:
            return 0.0
    
    def _format_time(self, seconds: float) -> str:
        """Formatar tempo em HH:MM:SS"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    def _clean_text(self, text: str) -> str:
        """Limpar texto"""
        if not text:
            return ""
        
        # Remover espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        # Capitalizar primeira letra
        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        return text

async def main():
    """Função principal simplificada"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        logger.info("🚀 Sistema de transcrição simples e eficaz")
        pipeline = SmartTranscriptionPipeline()
        
        start_time = time.time()
        result = await pipeline.process_audio(audio_path)
        processing_time = time.time() - start_time
        
        # Salvar se solicitado
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"💾 Salvo em: {output_file}")
        
        # Output JSON
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_time_seconds": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "model_used": "simple_efficient_pipeline"
        }
        
        print(json.dumps(output, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"💥 Erro: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())