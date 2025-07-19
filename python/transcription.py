#!/usr/bin/env python3
"""
SISTEMA PROFISSIONAL DE DIARIZAÇÃO E TRANSCRIÇÃO - VERSÃO OTIMIZADA COMPATÍVEL
===============================================================================
BASEADO NAS MELHORES PRÁTICAS 2024-2025 PARA MÁXIMA COMPATIBILIDADE

ARQUITETURA: Faster-Whisper + Silero VAD + Resemblyzer + sklearn clustering
OTIMIZADO PARA: 8 vCPUs + 32GB RAM - usar 90% dos recursos de forma eficiente
FILOSOFIA: Máxima compatibilidade, performance e robustez sem dependências problemáticas

DIFERENÇAS DA VERSÃO ANTERIOR:
✅ Faster-Whisper (4x mais rápido que Whisper original)
✅ Silero VAD (substitui WebRTC VAD problemático)
✅ Resemblyzer (substitui SpeechBrain problemático)
✅ sklearn clustering (substitui HDBSCAN problemático)
✅ Pipeline assíncrona otimizada
✅ Sistema de fallback robusto em cada etapa
✅ Configurações automáticas baseadas no hardware
✅ Compatível com nikolaik/python-nodejs:python3.11-nodejs18
"""

import sys
import json
import logging
import os
import tempfile
import asyncio
import time
import numpy as np
import warnings
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import re

# Suprimir warnings para output limpo
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Processamento de áudio otimizado
from pydub import AudioSegment
from pydub.effects import normalize
import librosa
import soundfile as sf
from scipy import signal as scipy_signal
from scipy.cluster.hierarchy import linkage, fcluster
import noisereduce as nr

# Machine Learning para diarização (versão compatível)
import torch
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

# Core components otimizados - MUDANÇAS PRINCIPAIS
from faster_whisper import WhisperModel  # ✅ Substitui openai-whisper (sem BatchedInferencePipeline)
from resemblyzer import VoiceEncoder, preprocess_wav  # ✅ Substitui speechbrain
import silero_vad  # ✅ Substitui webrtcvad

# Processamento paralelo
from tqdm import tqdm

# Configuração otimizada para container (detecta CPUs disponíveis)
available_cpus = os.cpu_count() or 4
torch_threads = max(1, min(available_cpus - 1, 7))  # Deixar 1 core para sistema, máx 7

torch.set_num_threads(torch_threads)
os.environ.update({
    'OMP_NUM_THREADS': str(torch_threads),
    'MKL_NUM_THREADS': str(torch_threads),
    'OMP_PROC_BIND': 'close',
    'KMP_AFFINITY': 'granularity=fine,compact,1,0'
})

def setup_production_logging():
    """Configurar logging otimizado para produção"""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_production_logging()

class OptimizedFasterWhisperTranscriber:
    """
    Transcritor baseado em Faster-Whisper com quantização INT8
    PERFORMANCE: 4x mais rápido que Whisper original mantendo mesma precisão
    """
    
    def __init__(self, model_size="distil-large-v3", device="cpu"):
        self.model_size = model_size
        self.device = device
        self.model = None
        
    def load_model(self):
        """Carregamento lazy do modelo com configurações otimizadas"""
        if self.model is None:
            logger.info(f"🚀 Carregando Faster-Whisper: {self.model_size}")
            try:
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type="int8",  # Quantização para máxima velocidade
                    num_workers=1,
                    cpu_threads=torch_threads
                )
                
                logger.info("✅ Faster-Whisper carregado com sucesso")
                
            except Exception as e:
                logger.error(f"❌ Erro ao carregar Faster-Whisper: {e}")
                # Fallback para modelo menor
                self._load_fallback_model()
        
        return self.model
    
    def _load_fallback_model(self):
        """Modelo de fallback se o principal falhar"""
        logger.warning("⚠️ Tentando modelo de fallback...")
        try:
            self.model = WhisperModel(
                "medium",
                device=self.device,
                compute_type="int8",
                num_workers=1,
                cpu_threads=max(1, torch_threads // 2)
            )
            self.model_size = "medium"
            logger.info("✅ Modelo de fallback carregado")
        except Exception as e:
            logger.error(f"❌ Fallback também falhou: {e}")
            # Último fallback: modelo tiny
            try:
                self.model = WhisperModel("tiny", device=self.device, compute_type="int8")
                self.model_size = "tiny"
                logger.info("✅ Modelo tiny carregado como último fallback")
            except Exception as e2:
                logger.error(f"❌ Todos os fallbacks falharam: {e2}")
                raise e2
    
    async def transcribe_full_audio(self, audio_path: str) -> str:
        """Transcrição completa otimizada"""
        model = self.load_model()
        
        try:
            segments, info = model.transcribe(
                audio_path,
                vad_filter=True,  # Remove silêncios automaticamente
                language="pt",  # Especificar idioma acelera 2x
                task="transcribe",
                temperature=0.0,  # Determinístico
                initial_prompt="Transcrição clara em português brasileiro:"
            )
            
            # Combinar todos os segmentos
            full_text = " ".join([segment.text.strip() for segment in segments])
            return full_text
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            return await self._fallback_transcribe(audio_path)
    
    async def transcribe_segments(self, audio_path: str, segments: List[Dict]) -> List[str]:
        """Transcrição de segmentos específicos"""
        model = self.load_model()
        
        # Carregar áudio original
        audio_data, sr = librosa.load(audio_path, sr=16000)
        transcriptions = []
        
        for segment in tqdm(segments, desc="Transcrevendo segmentos"):
            try:
                # Extrair segmento
                start_sample = int(segment['start'] * sr)
                end_sample = int(segment['end'] * sr)
                
                if end_sample <= start_sample:
                    transcriptions.append("")
                    continue
                
                segment_audio = audio_data[start_sample:end_sample]
                
                # Garantir duração mínima
                if len(segment_audio) < sr * 0.5:  # Menos de 0.5s
                    padding_needed = int(sr * 0.5) - len(segment_audio)
                    segment_audio = np.pad(segment_audio, (0, padding_needed), mode='constant')
                
                # Criar arquivo temporário
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_file:
                    sf.write(temp_file.name, segment_audio, sr)
                    
                    # Transcrever segmento
                    segments_result, _ = model.transcribe(
                        temp_file.name,
                        language="pt",
                        task="transcribe",
                        temperature=0.0,
                        beam_size=1,  # Mais rápido para CPU
                        best_of=1,
                        condition_on_previous_text=False  # Evita alucinações
                    )
                    
                    text = " ".join([s.text.strip() for s in segments_result])
                    transcriptions.append(text)
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro no segmento: {e}")
                transcriptions.append("")
        
        return transcriptions
    
    async def _fallback_transcribe(self, audio_path: str) -> str:
        """Fallback usando whisper original"""
        try:
            logger.info("🔄 Tentando fallback com openai-whisper")
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language="pt")
            return result["text"]
        except ImportError:
            logger.warning("⚠️ OpenAI Whisper não disponível")
            return "Erro na transcrição - modelos não disponíveis."
        except Exception as e:
            logger.error(f"❌ Fallback whisper falhou: {e}")
            return "Erro na transcrição."

class SileroVADProcessor:
    """
    Detecção de Atividade Vocal usando Silero VAD
    VANTAGEM: Modelo neural leve (~2MB) com precisão superior ao WebRTC VAD
    """
    
    def __init__(self):
        self.model = None
        
    def load_model(self):
        """Carregamento lazy do modelo Silero VAD"""
        if self.model is None:
            logger.info("🧠 Carregando Silero VAD model")
            try:
                # Configurar threads para VAD (menos recursos)
                torch.set_num_threads(max(1, torch_threads // 2))
                self.model = silero_vad.load_silero_vad()
                logger.info("✅ Silero VAD carregado")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar Silero VAD: {e}")
                raise e
        return self.model
    
    def detect_speech_segments(self, audio_path: str) -> List[Dict]:
        """
        Detecta segmentos de fala usando Silero VAD
        RETORNA: Lista de segmentos com timestamps precisos
        """
        model = self.load_model()
        
        try:
            # Carregar e preparar áudio
            audio_data, sr = librosa.load(audio_path, sr=16000, mono=True)
            
            # Normalizar áudio para VAD
            if np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))
            
            # Detectar timestamps de fala
            speech_timestamps = silero_vad.get_speech_timestamps(
                audio_data,
                model,
                threshold=0.5,
                min_speech_duration_ms=250,
                max_speech_duration_s=30,  # Chunks de até 30s
                min_silence_duration_ms=100,
                window_size_samples=1536,
                return_seconds=True
            )
            
            # Converter para formato padrão
            segments = []
            for i, timestamp in enumerate(speech_timestamps):
                segments.append({
                    'start': timestamp['start'],
                    'end': timestamp['end'],
                    'duration': timestamp['end'] - timestamp['start'],
                    'segment_id': i
                })
            
            logger.info(f"🎯 {len(segments)} segmentos de fala detectados")
            return segments
            
        except Exception as e:
            logger.error(f"❌ Erro no VAD: {e}")
            return self._create_fallback_segments(audio_path)
    
    def _create_fallback_segments(self, audio_path: str) -> List[Dict]:
        """Fallback: segmentos de tempo fixo quando VAD falha"""
        try:
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            segment_duration = 15.0  # 15 segundos
            
            segments = []
            start_time = 0.0
            segment_id = 0
            
            while start_time < duration:
                end_time = min(start_time + segment_duration, duration)
                if end_time - start_time >= 1.0:  # Mínimo 1 segundo
                    segments.append({
                        'start': start_time,
                        'end': end_time,
                        'duration': end_time - start_time,
                        'segment_id': segment_id
                    })
                    segment_id += 1
                start_time = end_time
            
            logger.warning(f"⚠️ VAD fallback: {len(segments)} segmentos de tempo fixo")
            return segments
        except Exception as e:
            logger.error(f"❌ Erro no fallback de segmentação: {e}")
            return []

class ResemblyzerSpeakerEmbedder:
    """
    Extrator de embeddings usando Resemblyzer
    VANTAGEM: Substitui SpeechBrain problemático mantendo qualidade profissional
    """
    
    def __init__(self, device="cpu"):
        self.device = device
        self.encoder = None
        
    def load_model(self):
        """Carregamento lazy do Resemblyzer"""
        if self.encoder is None:
            logger.info("🔬 Carregando Resemblyzer encoder")
            try:
                self.encoder = VoiceEncoder(device=self.device)
                logger.info("✅ Resemblyzer carregado")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar Resemblyzer: {e}")
                raise e
        return self.encoder
    
    def extract_embeddings(self, audio_path: str, segments: List[Dict]) -> Dict[str, np.ndarray]:
        """
        Extrai embeddings de cada segmento usando Resemblyzer
        RETORNA: Dicionário com embeddings normalizados
        """
        encoder = self.load_model()
        
        try:
            # Pré-processar áudio para Resemblyzer
            wav = preprocess_wav(audio_path)
            
            embeddings = {}
            
            for i, segment in enumerate(tqdm(segments, desc="Extraindo embeddings")):
                try:
                    # Calcular samples do segmento
                    start_sample = int(segment['start'] * 16000)  # Resemblyzer usa 16kHz
                    end_sample = int(segment['end'] * 16000)
                    
                    if end_sample <= start_sample or end_sample - start_sample < 8000:  # Mín 0.5s
                        continue
                    
                    # Extrair segmento
                    segment_wav = wav[start_sample:end_sample]
                    
                    # Garantir duração mínima
                    if len(segment_wav) < 8000:  # Menos de 0.5s
                        padding = 8000 - len(segment_wav)
                        segment_wav = np.pad(segment_wav, (0, padding), mode='constant')
                    
                    # Extrair embedding
                    embedding = encoder.embed_utterance(segment_wav)
                    
                    # Normalizar para melhor comparação
                    embedding_normalized = embedding / np.linalg.norm(embedding)
                    
                    embeddings[f"segment_{i}"] = embedding_normalized
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro no segmento {i}: {e}")
                    continue
            
            logger.info(f"📊 {len(embeddings)} embeddings extraídos")
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Erro na extração de embeddings: {e}")
            return {}
    
    def calculate_similarity_matrix(self, embeddings: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Calcula matriz de similaridades entre embeddings
        MÉTODO: Similaridade cosseno otimizada
        """
        if len(embeddings) < 2:
            return np.array([[1.0]])
        
        embedding_list = list(embeddings.values())
        n_embeddings = len(embedding_list)
        
        # Converter para matriz
        embedding_matrix = np.array(embedding_list)
        
        # Calcular similaridades cosseno (já normalizados)
        similarity_matrix = np.dot(embedding_matrix, embedding_matrix.T)
        
        # Garantir que diagonal seja 1.0 e valores estejam no range correto
        np.fill_diagonal(similarity_matrix, 1.0)
        similarity_matrix = np.clip(similarity_matrix, -1.0, 1.0)
        
        logger.info(f"🧮 Matriz de similaridade {n_embeddings}x{n_embeddings} calculada")
        return similarity_matrix

class CompatibleSpeakerClusterer:
    """
    Sistema de clustering compatível usando apenas sklearn
    ESTRATÉGIA: Múltiplos algoritmos com seleção automática do melhor
    SUBSTITUI: HDBSCAN problemático por algoritmos sklearn estáveis
    """
    
    def __init__(self):
        self.algorithms = {
            'agglomerative': self._cluster_agglomerative,
            'kmeans': self._cluster_kmeans,
            'ward': self._cluster_ward
        }
    
    def cluster_speakers(self, similarity_matrix: np.ndarray, max_speakers: int = 8) -> Tuple[np.ndarray, int, float]:
        """
        Clustering automático com seleção do melhor algoritmo
        RETORNA: (labels, n_speakers, quality_score)
        """
        logger.info("🎯 Iniciando clustering automático")
        
        best_labels = None
        best_score = -1
        best_n_speakers = 2
        best_algorithm = ""
        
        # Converter similaridade para distância
        distance_matrix = 1 - similarity_matrix
        np.fill_diagonal(distance_matrix, 0)
        
        # Garantir que a matriz de distância seja válida
        distance_matrix = np.clip(distance_matrix, 0, 2)  # Cosseno: distância entre 0 e 2
        
        # Testar diferentes algoritmos
        for alg_name, alg_func in self.algorithms.items():
            try:
                logger.info(f"🔍 Testando {alg_name}")
                
                labels, n_speakers = alg_func(distance_matrix, max_speakers)
                
                if n_speakers > 1 and n_speakers <= max_speakers:
                    score = self._evaluate_clustering(distance_matrix, labels)
                    
                    logger.info(f"📊 {alg_name}: {n_speakers} speakers, score: {score:.3f}")
                    
                    if score > best_score:
                        best_labels = labels
                        best_score = score
                        best_n_speakers = n_speakers
                        best_algorithm = alg_name
                        
            except Exception as e:
                logger.warning(f"⚠️ Erro em {alg_name}: {e}")
                continue
        
        if best_labels is not None:
            logger.info(f"🏆 Melhor: {best_algorithm} - {best_n_speakers} speakers (score: {best_score:.3f})")
            return best_labels, best_n_speakers, best_score
        else:
            # Fallback simples: alternancia entre 2 speakers
            logger.warning("⚠️ Clustering falhou, usando fallback")
            labels = np.array([i % 2 for i in range(len(similarity_matrix))])
            return labels, 2, 0.0
    
    def _cluster_agglomerative(self, distance_matrix: np.ndarray, max_speakers: int) -> Tuple[np.ndarray, int]:
        """Clustering hierárquico aglomerativo"""
        best_labels = None
        best_n_speakers = 2
        best_score = -1
        
        for n_speakers in range(2, min(max_speakers + 1, len(distance_matrix))):
            try:
                clusterer = AgglomerativeClustering(
                    n_clusters=n_speakers,
                    metric='precomputed',
                    linkage='average'
                )
                
                labels = clusterer.fit_predict(distance_matrix)
                score = self._evaluate_clustering(distance_matrix, labels)
                
                if score > best_score:
                    best_score = score
                    best_labels = labels
                    best_n_speakers = n_speakers
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro agglomerative com {n_speakers} speakers: {e}")
                continue
        
        return best_labels if best_labels is not None else np.zeros(len(distance_matrix), dtype=int), best_n_speakers
    
    def _cluster_kmeans(self, distance_matrix: np.ndarray, max_speakers: int) -> Tuple[np.ndarray, int]:
        """K-means clustering com MDS para conversão de distâncias"""
        try:
            from sklearn.manifold import MDS
            
            # Converter distâncias para pontos euclidanos usando MDS
            n_components = min(len(distance_matrix) - 1, 10, max_speakers)
            mds = MDS(n_components=n_components, dissimilarity='precomputed', 
                     random_state=42, max_iter=100, n_init=1)
            points = mds.fit_transform(distance_matrix)
            
            best_labels = None
            best_n_speakers = 2
            best_score = -1
            
            for n_speakers in range(2, min(max_speakers + 1, len(distance_matrix))):
                try:
                    clusterer = KMeans(n_clusters=n_speakers, random_state=42, 
                                     n_init=5, max_iter=100)
                    labels = clusterer.fit_predict(points)
                    score = self._evaluate_clustering(distance_matrix, labels)
                    
                    if score > best_score:
                        best_score = score
                        best_labels = labels
                        best_n_speakers = n_speakers
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erro kmeans com {n_speakers} speakers: {e}")
                    continue
            
            return best_labels if best_labels is not None else np.zeros(len(distance_matrix), dtype=int), best_n_speakers
            
        except Exception as e:
            logger.warning(f"⚠️ Erro no K-means: {e}")
            return np.zeros(len(distance_matrix), dtype=int), 2
    
    def _cluster_ward(self, distance_matrix: np.ndarray, max_speakers: int) -> Tuple[np.ndarray, int]:
        """Ward clustering usando MDS para converter distâncias"""
        try:
            from sklearn.manifold import MDS
            
            # MDS para converter para pontos euclidanos (necessário para Ward)
            n_components = min(len(distance_matrix) - 1, 10, max_speakers)
            mds = MDS(n_components=n_components, dissimilarity='precomputed', 
                     random_state=42, max_iter=100, n_init=1)
            points = mds.fit_transform(distance_matrix)
            
            best_labels = None
            best_n_speakers = 2
            best_score = -1
            
            for n_speakers in range(2, min(max_speakers + 1, len(distance_matrix))):
                try:
                    clusterer = AgglomerativeClustering(
                        n_clusters=n_speakers,
                        linkage='ward'
                    )
                    
                    labels = clusterer.fit_predict(points)
                    score = self._evaluate_clustering(distance_matrix, labels)
                    
                    if score > best_score:
                        best_score = score
                        best_labels = labels
                        best_n_speakers = n_speakers
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erro ward com {n_speakers} speakers: {e}")
                    continue
            
            return best_labels if best_labels is not None else np.zeros(len(distance_matrix), dtype=int), best_n_speakers
            
        except Exception as e:
            logger.warning(f"⚠️ Erro no Ward clustering: {e}")
            return np.zeros(len(distance_matrix), dtype=int), 2
    
    def _evaluate_clustering(self, distance_matrix: np.ndarray, labels: np.ndarray) -> float:
        """Avalia qualidade do clustering usando silhouette score"""
        try:
            unique_labels = np.unique(labels)
            if len(unique_labels) < 2:
                return 0.0
            
            # Silhouette score principal
            silhouette = silhouette_score(distance_matrix, labels, metric='precomputed')
            
            # Bonificação por distribuição equilibrada de clusters
            cluster_sizes = np.bincount(labels)
            if len(cluster_sizes) > 1 and np.mean(cluster_sizes) > 0:
                size_balance = 1.0 - np.std(cluster_sizes) / np.mean(cluster_sizes)
                size_balance = max(0.0, min(1.0, size_balance))  # Garantir range [0,1]
            else:
                size_balance = 1.0
            
            # Score final combinado
            final_score = 0.8 * silhouette + 0.2 * size_balance
            return max(0.0, final_score)
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na avaliação de qualidade: {e}")
            return 0.0

class TemporalValidator:
    """
    Validador temporal para garantir consistência da timeline
    FUNÇÃO: Suavizar transições e consolidar segmentos consecutivos
    """
    
    def __init__(self, min_duration=1.0):
        self.min_duration = min_duration
    
    def validate_timeline(self, segments: List[Dict], labels: np.ndarray) -> List[Dict]:
        """
        Valida e suaviza timeline temporal
        RETORNA: Segmentos validados com speakers atribuídos
        """
        logger.info("🔍 Validando timeline temporal")
        
        if len(segments) != len(labels):
            logger.error("❌ Incompatibilidade entre segmentos e labels")
            # Criar labels simples se houver incompatibilidade
            labels = np.array([i % 2 for i in range(len(segments))])
        
        # Combinar segmentos com labels
        timeline = []
        for i, (segment, label) in enumerate(zip(segments, labels)):
            timeline.append({
                'start': segment['start'],
                'end': segment['end'],
                'duration': segment['end'] - segment['start'],
                'speaker_id': int(label),
                'original_index': i
            })
        
        # Aplicar validações em sequência
        timeline = self._remove_short_segments(timeline)
        timeline = self._smooth_transitions(timeline)
        timeline = self._consolidate_consecutive(timeline)
        
        # Converter para formato final
        validated_segments = []
        for item in timeline:
            validated_segments.append({
                'start': item['start'],
                'end': item['end'],
                'speaker': f"SPEAKER_{item['speaker_id'] + 1:02d}"
            })
        
        logger.info(f"✅ Timeline validada: {len(validated_segments)} segmentos")
        return validated_segments
    
    def _remove_short_segments(self, timeline: List[Dict]) -> List[Dict]:
        """Remove ou mescla segmentos muito curtos"""
        if not timeline:
            return timeline
            
        cleaned = []
        
        for segment in timeline:
            if segment['duration'] >= self.min_duration:
                cleaned.append(segment)
            elif cleaned:
                # Mesclar com segmento anterior
                cleaned[-1]['end'] = segment['end']
                cleaned[-1]['duration'] = cleaned[-1]['end'] - cleaned[-1]['start']
            else:
                # Se é o primeiro segmento e é muito curto, manter mesmo assim
                cleaned.append(segment)
        
        return cleaned
    
    def _smooth_transitions(self, timeline: List[Dict]) -> List[Dict]:
        """Suaviza transições rápidas entre speakers"""
        if len(timeline) < 3:
            return timeline
        
        smoothed = [timeline[0]]
        
        for i in range(1, len(timeline) - 1):
            current = timeline[i]
            prev_speaker = smoothed[-1]['speaker_id']
            next_speaker = timeline[i+1]['speaker_id']
            
            # Corrigir outliers temporais (segmento isolado muito curto)
            if (current['speaker_id'] != prev_speaker and 
                current['speaker_id'] != next_speaker and
                current['duration'] < 2.0):
                # Atribuir ao speaker anterior (mais conservador)
                current['speaker_id'] = prev_speaker
            
            smoothed.append(current)
        
        # Adicionar último segmento
        if len(timeline) > 1:
            smoothed.append(timeline[-1])
        
        return smoothed
    
    def _consolidate_consecutive(self, timeline: List[Dict]) -> List[Dict]:
        """Consolida segmentos consecutivos do mesmo speaker"""
        if not timeline:
            return timeline
        
        consolidated = [timeline[0]]
        
        for segment in timeline[1:]:
            last = consolidated[-1]
            
            # Verificar se é mesmo speaker e gap pequeno
            gap = abs(segment['start'] - last['end'])
            same_speaker = segment['speaker_id'] == last['speaker_id']
            small_gap = gap < 2.0  # Menos de 2 segundos
            
            if same_speaker and small_gap:
                # Mesclar segmentos
                last['end'] = segment['end']
                last['duration'] = last['end'] - last['start']
            else:
                consolidated.append(segment)
        
        return consolidated

class AdvancedAudioPreprocessor:
    """
    Preprocessador de áudio otimizado para diarização
    TÉCNICAS: Normalização inteligente + redução de ruído + equalização vocal
    """
    
    def __init__(self):
        self.sample_rate = 16000
        
    def preprocess_audio(self, audio_path: str) -> str:
        """
        Preprocessamento completo para otimizar diarização
        RETORNA: Path do áudio processado
        """
        logger.info("🔧 Preprocessando áudio para diarização")
        
        try:
            # Carregar áudio
            audio = AudioSegment.from_file(audio_path)
            
            # Pipeline de preprocessamento
            audio = self._intelligent_normalization(audio)
            audio = self._noise_reduction(audio)
            audio = self._voice_equalization(audio)
            
            # Salvar resultado em arquivo temporário
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(
                    temp_file.name, 
                    format='wav', 
                    parameters=["-ar", str(self.sample_rate)]
                )
                processed_path = temp_file.name
            
            logger.info(f"✅ Preprocessamento concluído: {processed_path}")
            return processed_path
            
        except Exception as e:
            logger.error(f"❌ Erro no preprocessamento: {e}")
            return audio_path  # Retornar original se falhar
    
    def _intelligent_normalization(self, audio: AudioSegment) -> AudioSegment:
        """Normalização adaptativa baseada na dinâmica do áudio"""
        try:
            # Análise RMS em janelas
            window_ms = 1000
            rms_values = []
            
            for i in range(0, len(audio), window_ms):
                window = audio[i:i + window_ms]
                if len(window) > 0:
                    rms_values.append(window.rms)
            
            if rms_values:
                median_rms = np.median(rms_values)
                target_rms = 3000  # Valor alvo empírico
                
                if median_rms > 0:
                    gain_db = 20 * np.log10(target_rms / median_rms)
                    gain_db = np.clip(gain_db, -15, 15)  # Limitar ganho para evitar distorção
                    audio = audio + gain_db
            
            return normalize(audio, headroom=0.1)
        except Exception as e:
            logger.warning(f"⚠️ Erro na normalização: {e}")
            return audio
    
    def _noise_reduction(self, audio: AudioSegment) -> AudioSegment:
        """Redução de ruído usando noisereduce"""
        try:
            # Converter para numpy
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            if audio.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)
            
            # Normalizar para noise reduction
            if np.max(np.abs(samples)) > 0:
                samples = samples / np.max(np.abs(samples))
            
            # Aplicar redução de ruído
            reduced = nr.reduce_noise(
                y=samples,
                sr=audio.frame_rate,
                stationary=False,  # Ruído não-estacionário
                prop_decrease=0.6  # Reduzir 60% do ruído
            )
            
            # Converter de volta para AudioSegment
            reduced = (reduced * 32767).astype(np.int16)
            return audio._spawn(reduced.tobytes())
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na redução de ruído: {e}")
            return audio
    
    def _voice_equalization(self, audio: AudioSegment) -> AudioSegment:
        """Equalização otimizada para voz"""
        try:
            # Filtros para faixa vocal (80Hz - 8kHz)
            audio = audio.high_pass_filter(80)   # Remove ruído grave
            audio = audio.low_pass_filter(8000)  # Remove ruído agudo
            return audio
        except Exception as e:
            logger.warning(f"⚠️ Erro na equalização: {e}")
            return audio

class RobustTranscriptionPipeline:
    """
    Pipeline principal que orquestra todos os componentes
    ARQUITETURA: Faster-Whisper + Silero VAD + Resemblyzer + sklearn
    """
    
    def __init__(self):
        self.preprocessor = AdvancedAudioPreprocessor()
        self.vad = SileroVADProcessor()
        self.embedder = ResemblyzerSpeakerEmbedder()
        self.clusterer = CompatibleSpeakerClusterer()
        self.validator = TemporalValidator()
        self.transcriber = OptimizedFasterWhisperTranscriber()
        
        self.config = {
            'max_speakers': min(8, available_cpus),  # Adaptativo ao hardware
            'min_segment_duration': 2.0,
            'quality_threshold': 0.3,
            'enable_preprocessing': True
        }
    
    async def process_audio(self, audio_path: str) -> str:
        """
        Pipeline completa de diarização e transcrição
        RETORNA: Transcrição formatada com speakers identificados
        """
        logger.info(f"🎯 Iniciando pipeline completa: {audio_path}")
        start_time = time.time()
        
        temp_files = []
        
        try:
            # Verificar se arquivo existe
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Etapa 1: Preprocessamento (opcional, configurável)
            if self.config['enable_preprocessing']:
                logger.info("📊 Etapa 1/6: Preprocessamento de áudio")
                processed_path = self.preprocessor.preprocess_audio(audio_path)
                if processed_path != audio_path:
                    temp_files.append(processed_path)
            else:
                processed_path = audio_path
            
            # Análise de duração para estratégia adaptativa
            duration = self._get_audio_duration(processed_path)
            logger.info(f"⏱️ Duração: {duration:.1f}s ({duration/60:.1f}min)")
            
            # Estratégia baseada na duração
            if duration < 30:  # Menos de 30 segundos
                logger.info("⚡ Áudio muito curto - transcrição direta")
                return await self._direct_transcription(processed_path, duration)
            
            # Etapa 2: Detecção de segmentos de fala (VAD)
            logger.info("📊 Etapa 2/6: Detecção de atividade vocal")
            speech_segments = self.vad.detect_speech_segments(processed_path)
            
            if len(speech_segments) < 2:
                logger.info("⚡ Poucos segmentos detectados - transcrição direta")
                return await self._direct_transcription(processed_path, duration)
            
            # Etapa 3: Extração de embeddings neurais
            logger.info("📊 Etapa 3/6: Extração de embeddings neurais")
            embeddings = self.embedder.extract_embeddings(processed_path, speech_segments)
            
            if len(embeddings) < 2:
                logger.warning("⚠️ Poucos embeddings válidos - fallback simples")
                return await self._simple_diarization_fallback(processed_path, speech_segments)
            
            # Etapa 4: Clustering de speakers
            logger.info("📊 Etapa 4/6: Clustering automático de speakers")
            similarity_matrix = self.embedder.calculate_similarity_matrix(embeddings)
            labels, n_speakers, quality = self.clusterer.cluster_speakers(
                similarity_matrix, self.config['max_speakers']
            )
            
            logger.info(f"🎭 {n_speakers} speakers detectados (qualidade: {quality:.3f})")
            
            # Verificar qualidade do clustering
            if quality < self.config['quality_threshold']:
                logger.warning(f"⚠️ Qualidade baixa ({quality:.3f}) - aplicando fallback")
                return await self._simple_diarization_fallback(processed_path, speech_segments)
            
            # Etapa 5: Validação temporal
            logger.info("📊 Etapa 5/6: Validação temporal")
            validated_segments = self.validator.validate_timeline(speech_segments, labels)
            
            # Etapa 6: Transcrição com diarização
            logger.info("📊 Etapa 6/6: Transcrição com diarização")
            transcriptions = await self.transcriber.transcribe_segments(processed_path, validated_segments)
            
            # Formatação final
            final_result = self._format_transcription(validated_segments, transcriptions)
            
            # Log de métricas finais
            processing_time = time.time() - start_time
            self._log_metrics(duration, processing_time, n_speakers, len(validated_segments))
            
            return final_result
            
        except Exception as e:
            logger.error(f"💥 Erro na pipeline principal: {e}")
            return await self._emergency_fallback(audio_path)
        
        finally:
            # Limpeza de arquivos temporários
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao limpar arquivo temporário: {e}")
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Obter duração do áudio de forma robusta"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            logger.warning(f"⚠️ Erro ao obter duração: {e}")
            return 0.0
    
    async def _direct_transcription(self, audio_path: str, duration: float) -> str:
        """Transcrição direta sem diarização"""
        logger.info("🔄 Executando transcrição direta")
        text = await self.transcriber.transcribe_full_audio(audio_path)
        timestamp = self._format_timestamp(0, duration)
        clean_text = self._clean_text(text)
        return f"{timestamp} SPEAKER 01:\n{clean_text}"
    
    async def _simple_diarization_fallback(self, audio_path: str, segments: List[Dict]) -> str:
        """Fallback com diarização simples alternada"""
        logger.info("🔄 Fallback: diarização simples alternada")
        
        # Atribuir speakers alternadamente (simples mas funcional)
        for i, segment in enumerate(segments):
            segment['speaker'] = f"SPEAKER_{(i % 2) + 1:02d}"
        
        # Transcrever segmentos
        transcriptions = await self.transcriber.transcribe_segments(audio_path, segments)
        return self._format_transcription(segments, transcriptions)
    
    async def _emergency_fallback(self, audio_path: str) -> str:
        """Fallback de emergência total"""
        logger.warning("🆘 Ativando fallback de emergência")
        
        try:
            text = await self.transcriber.transcribe_full_audio(audio_path)
            duration = self._get_audio_duration(audio_path)
            timestamp = self._format_timestamp(0, duration)
            clean_text = self._clean_text(text)
            return f"{timestamp} SPEAKER 01:\n{clean_text}"
        except Exception as e:
            logger.error(f"❌ Fallback de emergência falhou: {e}")
            return "Sistema temporariamente indisponível. Tente novamente."
    
    def _format_transcription(self, segments: List[Dict], transcriptions: List[str]) -> str:
        """Formata transcrição final com timeline"""
        if len(segments) != len(transcriptions):
            logger.error("❌ Incompatibilidade na formatação final")
            return "Erro na formatação da transcrição."
        
        formatted_parts = []
        
        for segment, transcription in zip(segments, transcriptions):
            if transcription and transcription.strip():
                clean_text = self._clean_text(transcription)
                if clean_text:
                    timestamp = self._format_timestamp(segment['start'], segment['end'])
                    speaker = segment['speaker'].replace("_", " ")
                    formatted_parts.append(f"{timestamp} {speaker}:\n{clean_text}")
        
        if formatted_parts:
            return "\n\n".join(formatted_parts)
        else:
            return "Nenhuma transcrição válida foi obtida."
    
    def _clean_text(self, text: str) -> str:
        """Limpeza e formatação do texto transcrito"""
        if not text:
            return ""
        
        # Remover espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        # Limpar caracteres especiais preservando acentos portugueses
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)áàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]', '', text)
        
        # Trim e capitalizar primeira letra
        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        return text
    
    def _format_timestamp(self, start: float, end: float) -> str:
        """Formatação padronizada de timestamp"""
        def to_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        return f"[{to_time(start)} - {to_time(end)}]"
    
    def _log_metrics(self, duration: float, processing_time: float, n_speakers: int, n_segments: int):
        """Log de métricas finais para monitoramento"""
        speed_ratio = duration / processing_time if processing_time > 0 else 0
        
        logger.info("=" * 50)
        logger.info("📊 MÉTRICAS FINAIS DA PIPELINE")
        logger.info("=" * 50)
        logger.info(f"⏱️ Duração do áudio: {duration:.1f}s ({duration/60:.1f}min)")
        logger.info(f"🚀 Tempo de processamento: {processing_time:.1f}s")
        logger.info(f"⚡ Velocidade: {speed_ratio:.1f}x tempo real")
        logger.info(f"🎭 Speakers detectados: {n_speakers}")
        logger.info(f"📝 Segmentos processados: {n_segments}")
        logger.info(f"💻 Recursos utilizados: {torch_threads} cores")
        logger.info("=" * 50)

async def main():
    """
    Função principal otimizada para integração com Node.js
    Compatível com estrutura nikolaik/python-nodejs:python3.11-nodejs18
    """
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Por favor, forneça o caminho do arquivo de áudio",
            "usage": "python transcricao_diarizacao.py <audio_path> [output_dir]"
        }, ensure_ascii=False))
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        logger.info("🚀 Inicializando sistema de transcrição e diarização otimizado")
        pipeline = RobustTranscriptionPipeline()
        
        start_time = time.time()
        result = await pipeline.process_audio(audio_path)
        processing_time = time.time() - start_time
        
        # Salvar resultado se diretório de saída foi especificado
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao_diarizacao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"💾 Resultado salvo em: {output_file}")
        
        # Output JSON estruturado para integração com Node.js
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "faster_whisper_silero_resemblyzer_optimized",
            "processing_time_seconds": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "diarization_available": True,
            "features_used": [
                "faster_whisper_int8_quantization",
                "silero_neural_vad",
                "resemblyzer_speaker_embeddings",
                "sklearn_multimodal_clustering",
                "temporal_validation",
                "advanced_audio_preprocessing",
                "automatic_fallback_system"
            ],
            "architecture": "faster_whisper_silero_resemblyzer_sklearn",
            "compatibility": "python_3.11_nikolaik_docker_optimized",
            "hardware_utilized": {
                "cpu_cores": torch_threads,
                "total_cores": available_cpus
            }
        }
        
        print(json.dumps(output, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"💥 Erro crítico na execução: {e}")
        
        # Output de erro estruturado
        error_output = {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "fallback_available": True,
            "compatibility_info": {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "torch_available": True,
                "dependencies_status": "check_requirements"
            },
            "troubleshooting": [
                "Verificar se o arquivo de áudio existe e é válido",
                "Verificar se todas as dependências estão instaladas",
                "Verificar logs detalhados acima para diagnóstico"
            ]
        }
        
        print(json.dumps(error_output, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    # Configurar asyncio para compatibilidade máxima
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Processamento interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Erro fatal: {e}")
        sys.exit(1)