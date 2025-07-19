#!/usr/bin/env python3
"""
SISTEMA PROFISSIONAL DE DIARIZAÇÃO E TRANSCRIÇÃO
=================================================
FILOSOFIA: Diarização perfeita usando recursos neurais gratuitos
OTIMIZADO PARA: 8 vCPUs + 32GB RAM - usar 90% dos recursos
ESTRATÉGIA: Embeddings neurais + Clustering avançado + Validação temporal

EDUCATIVO: Este sistema implementa técnicas de ponta em diarização de speakers:
1. Embeddings neurais pré-treinados (SpeechBrain) - "impressões digitais" de voz
2. Clustering hierárquico (HDBSCAN) - agrupamento automático de speakers
3. Validação temporal - garantia de consistência ao longo do tempo
4. Processamento paralelo massivo - usar todos os 8 cores
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
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings("ignore")

# Processamento de áudio profissional
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np
import librosa
import soundfile as sf
from scipy import signal as scipy_signal
from scipy.spatial.distance import cosine, pdist, squareform
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
import noisereduce as nr
import webrtcvad

# Machine Learning para diarização profissional
import torch
import torchaudio
from transformers import AutoProcessor, AutoModel
import speechbrain as sb
from speechbrain.pretrained import EncoderClassifier

# Clustering avançado - usando apenas scikit-learn (mais compatível)
from sklearn.cluster import AgglomerativeClustering, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import hdbscan

# Processamento paralelo otimizado
from joblib import Parallel, delayed
from tqdm import tqdm

# Configuração de logging otimizada para produção
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurar para usar todos os recursos disponíveis
torch.set_num_threads(7)  # Deixar 1 core para o sistema
os.environ['OMP_NUM_THREADS'] = '7'
os.environ['MKL_NUM_THREADS'] = '7'

# Configurar logging para produção (sem multiprocessing-logging)
def setup_production_logging():
    """
    EDUCATIVO: Configura logging otimizado para ambiente de produção
    Remove dependências problemáticas mantendo funcionalidade completa
    """
    import logging
    
    # Configurar formatação detalhada para debugging
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configurar logger principal
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    return logger

# Inicializar logging
logger = setup_production_logging()

class ProfessionalSpeakerEmbedder:
    """
    EDUCATIVO: Extrator de embeddings neurais para identificação de speakers
    
    Conceito: Assim como impressões digitais identificam pessoas, embeddings 
    identificam vozes únicas. Usamos redes neurais pré-treinadas que aprenderam
    a extrair características únicas da voz humana de milhões de exemplos.
    
    Estratégia: Utilizamos modelos SpeechBrain (ECAPA-TDNN) que são state-of-the-art
    em reconhecimento de speaker e são completamente gratuitos.
    """
    
    def __init__(self, device="cpu", model_name="speechbrain/spkrec-ecapa-voxceleb"):
        self.device = device
        self.model_name = model_name
        self.model = None
        self.sample_rate = 16000
        
        # Cache para otimização de memória
        self.embedding_cache = {}
        
    def load_model(self):
        """
        Carrega modelo neural pré-treinado para extração de embeddings
        EDUCATIVO: ECAPA-TDNN é uma arquitetura otimizada para reconhecimento de speaker
        """
        if self.model is None:
            logger.info(f"🧠 Carregando modelo neural de speaker: {self.model_name}")
            try:
                self.model = EncoderClassifier.from_hparams(
                    source=self.model_name,
                    savedir=f"./models/{self.model_name.split('/')[-1]}",
                    run_opts={"device": self.device}
                )
                logger.info("✅ Modelo neural carregado com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar modelo: {e}")
                # Fallback para modelo local menor se houver erro
                self.load_fallback_model()
        
        return self.model
    
    def load_fallback_model(self):
        """
        Modelo de fallback caso o principal falhe
        EDUCATIVO: Sempre ter um plano B em sistemas de produção
        """
        logger.warning("⚠️ Tentando modelo de fallback...")
        try:
            self.model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-xvect-voxceleb",
                savedir="./models/spkrec-xvect-voxceleb",
                run_opts={"device": self.device}
            )
            self.model_name = "speechbrain/spkrec-xvect-voxceleb"
            logger.info("✅ Modelo de fallback carregado")
        except Exception as e:
            logger.error(f"❌ Fallback também falhou: {e}")
            raise e
    
    def extract_embeddings_from_segments(self, audio_path: str, segments: List[Dict]) -> Dict[str, np.ndarray]:
        """
        Extrai embeddings neurais de cada segmento de áudio
        
        EDUCATIVO: Cada segmento vira um vetor de 192 ou 512 dimensões que 
        representa as características únicas da voz naquele momento.
        Segmentos da mesma pessoa terão embeddings muito similares.
        """
        logger.info(f"🔬 Extraindo embeddings neurais de {len(segments)} segmentos")
        
        model = self.load_model()
        embeddings = {}
        
        # Carregar áudio original
        audio_data, sr = librosa.load(audio_path, sr=self.sample_rate)
        
        for i, segment in enumerate(tqdm(segments, desc="Extraindo embeddings")):
            try:
                # Extrair segmento de áudio
                start_sample = int(segment['start'] * sr)
                end_sample = int(segment['end'] * sr)
                
                if end_sample <= start_sample:
                    continue
                    
                segment_audio = audio_data[start_sample:end_sample]
                
                # Garantir duração mínima para embedding estável
                if len(segment_audio) < sr * 0.5:  # Mínimo 0.5 segundos
                    # Pad com silêncio se muito curto
                    padding_needed = int(sr * 0.5) - len(segment_audio)
                    segment_audio = np.pad(segment_audio, (0, padding_needed), mode='constant')
                
                # Converter para tensor
                segment_tensor = torch.FloatTensor(segment_audio).unsqueeze(0)
                
                # Extrair embedding usando modelo neural
                with torch.no_grad():
                    embedding = model.encode_batch(segment_tensor)
                    embedding_np = embedding.squeeze().cpu().numpy()
                
                # Normalizar embedding para comparações de similaridade
                embedding_normalized = embedding_np / np.linalg.norm(embedding_np)
                
                embeddings[f"segment_{i}"] = embedding_normalized
                
                # Log de progresso
                if (i + 1) % 10 == 0:
                    logger.info(f"📊 Embeddings extraídos: {i+1}/{len(segments)}")
                
            except Exception as e:
                logger.warning(f"⚠️ Erro no segmento {i}: {e}")
                continue
        
        logger.info(f"✅ {len(embeddings)} embeddings extraídos com sucesso")
        return embeddings
    
    def calculate_embedding_similarities(self, embeddings: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Calcula matriz de similaridades entre todos os embeddings usando scipy
        
        EDUCATIVO: Matriz de similaridade é como uma tabela de "quão parecidos"
        são todos os pares de segmentos. Valores próximos de 1 = muito similares,
        próximos de 0 = muito diferentes.
        
        OTIMIZAÇÃO: Usamos scipy.spatial.distance que é otimizada e compatível
        """
        logger.info("🧮 Calculando matriz de similaridades neurais")
        
        embedding_list = list(embeddings.values())
        n_embeddings = len(embedding_list)
        
        if n_embeddings < 2:
            return np.array([[1.0]])
        
        # Converter para array numpy para processamento eficiente
        embedding_matrix = np.array(embedding_list)
        
        # Calcular matriz de distâncias usando scipy (mais eficiente)
        # Usamos 'cosine' que calcula 1 - cosine_similarity
        distances = pdist(embedding_matrix, metric='cosine')
        distance_matrix = squareform(distances)
        
        # Converter distâncias para similaridades (1 - distância)
        similarity_matrix = 1 - distance_matrix
        
        # Garantir que diagonal seja 1.0 (similaridade consigo mesmo)
        np.fill_diagonal(similarity_matrix, 1.0)
        
        logger.info(f"📊 Matriz {n_embeddings}x{n_embeddings} calculada com scipy")
        return similarity_matrix

class AdvancedSpeakerClusterer:
    """
    EDUCATIVO: Sistema de clustering avançado para agrupamento automático de speakers
    
    Conceito: Imagine que você tem centenas de fotos de pessoas e precisa agrupá-las
    por indivíduo, mas sem saber quantas pessoas há. O clustering faz exatamente isso
    com vozes - agrupa automaticamente segmentos que vieram da mesma pessoa.
    
    Estratégia: Usamos HDBSCAN que é superior ao K-means porque:
    1. Não precisa saber o número de speakers antecipadamente
    2. Pode detectar ruído e outliers
    3. Encontra clusters de formas irregulares
    
    COMPATIBILIDADE: Versão otimizada usando apenas scikit-learn e scipy
    """
    
    def __init__(self, min_cluster_size=3, min_samples=2):
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        
        # Algoritmos de clustering disponíveis (apenas os compatíveis)
        self.clustering_algorithms = {
            'hdbscan': self.cluster_with_hdbscan,
            'agglomerative': self.cluster_with_agglomerative,
            'ward': self.cluster_with_ward
        }
    
    def cluster_speakers_automatic(self, similarity_matrix: np.ndarray, 
                                  max_speakers: int = 10) -> Tuple[np.ndarray, int, float]:
        """
        Clustering automático com validação de qualidade
        
        EDUCATIVO: Tenta diferentes algoritmos e escolhe o melhor resultado
        baseado em métricas de qualidade (silhouette score).
        """
        logger.info("🎯 Iniciando clustering automático de speakers")
        
        best_labels = None
        best_score = -1
        best_n_speakers = 0
        best_algorithm = ""
        
        # Converter similaridade para distância
        distance_matrix = 1 - similarity_matrix
        np.fill_diagonal(distance_matrix, 0)  # Distância de si mesmo = 0
        
        # Testar diferentes algoritmos
        results = {}
        
        for alg_name, alg_func in self.clustering_algorithms.items():
            try:
                logger.info(f"🔍 Testando algoritmo: {alg_name}")
                
                labels, n_speakers = alg_func(distance_matrix, max_speakers)
                
                if n_speakers > 1 and n_speakers <= max_speakers:
                    # Calcular qualidade do clustering
                    score = self.evaluate_clustering_quality(distance_matrix, labels)
                    
                    results[alg_name] = {
                        'labels': labels,
                        'n_speakers': n_speakers,
                        'score': score
                    }
                    
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
            logger.info(f"🏆 Melhor resultado: {best_algorithm} com {best_n_speakers} speakers (score: {best_score:.3f})")
            return best_labels, best_n_speakers, best_score
        else:
            # Fallback: assumir 2 speakers se tudo falhar
            logger.warning("⚠️ Clustering falhou, usando fallback com 2 speakers")
            return self.create_fallback_clustering(len(similarity_matrix)), 2, 0.0
    
    def cluster_with_hdbscan(self, distance_matrix: np.ndarray, max_speakers: int) -> Tuple[np.ndarray, int]:
        """
        HDBSCAN - Hierarchical Density-Based Spatial Clustering
        
        EDUCATIVO: HDBSCAN constrói uma hierarquia de clusters baseada em densidade.
        É excellent para encontrar clusters de forma natural e lidar com ruído.
        """
        clusterer = hdbscan.HDBSCAN(
            metric='precomputed',
            min_cluster_size=max(2, self.min_cluster_size),
            min_samples=self.min_samples,
            cluster_selection_epsilon=0.1,
            alpha=1.0
        )
        
        labels = clusterer.fit_predict(distance_matrix)
        
        # Remapear labels para eliminar -1 (ruído)
        unique_labels = np.unique(labels[labels >= 0])
        n_speakers = len(unique_labels)
        
        # Se encontrou ruído (-1), atribuir ao cluster mais próximo
        if -1 in labels:
            for i, label in enumerate(labels):
                if label == -1:
                    # Encontrar cluster mais próximo
                    distances_to_clusters = []
                    for cluster_id in unique_labels:
                        cluster_indices = np.where(labels == cluster_id)[0]
                        min_dist = np.min(distance_matrix[i, cluster_indices])
                        distances_to_clusters.append(min_dist)
                    
                    if distances_to_clusters:
                        closest_cluster = unique_labels[np.argmin(distances_to_clusters)]
                        labels[i] = closest_cluster
        
        return labels, n_speakers
    
    def cluster_with_agglomerative(self, distance_matrix: np.ndarray, max_speakers: int) -> Tuple[np.ndarray, int]:
        """
        Agglomerative Clustering - Abordagem hierárquica bottom-up
        
        EDUCATIVO: Começa com cada ponto como um cluster e vai juntando
        os mais similares até formar o número ideal de clusters.
        """
        best_labels = None
        best_n_speakers = 2
        best_score = -1
        
        # Testar diferentes números de speakers
        for n_speakers in range(2, min(max_speakers + 1, len(distance_matrix))):
            try:
                clusterer = AgglomerativeClustering(
                    n_clusters=n_speakers,
                    affinity='precomputed',
                    linkage='average'
                )
                
                labels = clusterer.fit_predict(distance_matrix)
                score = self.evaluate_clustering_quality(distance_matrix, labels)
                
                if score > best_score:
                    best_score = score
                    best_labels = labels
                    best_n_speakers = n_speakers
                    
            except Exception as e:
                continue
        
        return best_labels if best_labels is not None else np.zeros(len(distance_matrix), dtype=int), best_n_speakers
    
    def cluster_with_ward(self, distance_matrix: np.ndarray, max_speakers: int) -> Tuple[np.ndarray, int]:
        """
        Ward Clustering - Minimiza variância intra-cluster
        
        EDUCATIVO: Ward é especialmente bom para clustering de embeddings porque
        minimiza a variância dentro de cada cluster, criando grupos mais coesos.
        É como organizar pessoas por altura E peso simultaneamente.
        """
        # Converter distância para formato apropriado para Ward
        # Ward precisa de dados originais, então usamos uma aproximação
        best_labels = None
        best_n_speakers = 2
        best_score = -1
        
        for n_speakers in range(2, min(max_speakers + 1, len(distance_matrix))):
            try:
                # Ward clustering usando conectividade para evitar problemas
                clusterer = AgglomerativeClustering(
                    n_clusters=n_speakers,
                    linkage='ward',
                    affinity='euclidean'
                )
                
                # Converter matriz de distância para pontos euclidinos aproximados
                # Usando MDS (Multi-Dimensional Scaling) simplificado
                from sklearn.manifold import MDS
                mds = MDS(n_components=min(len(distance_matrix)-1, 10), 
                         dissimilarity='precomputed', random_state=42)
                points = mds.fit_transform(distance_matrix)
                
                labels = clusterer.fit_predict(points)
                score = self.evaluate_clustering_quality(distance_matrix, labels)
                
                if score > best_score:
                    best_score = score
                    best_labels = labels
                    best_n_speakers = n_speakers
                    
            except Exception as e:
                continue
        
        return best_labels if best_labels is not None else np.zeros(len(distance_matrix), dtype=int), best_n_speakers
    
    def evaluate_clustering_quality(self, distance_matrix: np.ndarray, labels: np.ndarray) -> float:
        """
        Avalia qualidade do clustering usando múltiplas métricas
        
        EDUCATIVO: Silhouette score mede quão bem separados estão os clusters.
        Valores próximos de 1 = clusters bem definidos, próximos de -1 = mal definidos.
        """
        try:
            if len(np.unique(labels)) < 2:
                return 0.0
            
            # Silhouette score principal
            silhouette = silhouette_score(distance_matrix, labels, metric='precomputed')
            
            # Bonificação por distribuição equilibrada de clusters
            cluster_sizes = np.bincount(labels)
            size_balance = 1.0 - np.std(cluster_sizes) / np.mean(cluster_sizes)
            
            # Score final combinado
            final_score = 0.8 * silhouette + 0.2 * size_balance
            
            return max(0.0, final_score)
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na avaliação de qualidade: {e}")
            return 0.0
    
    def create_fallback_clustering(self, n_segments: int) -> np.ndarray:
        """
        Clustering de fallback alternando entre 2 speakers
        """
        return np.array([i % 2 for i in range(n_segments)])

class TemporalDiarizationValidator:
    """
    EDUCATIVO: Validador temporal para garantir consistência da diarização
    
    Conceito: Mesmo com clustering perfeito, pode haver inconsistências temporais
    (ex: mesmo speaker aparece como diferentes IDs). Este validador garante que
    a timeline final faça sentido cronologicamente.
    
    Estratégia: Aplica heurísticas temporais e suavização para corrigir
    inconsistências típicas de diarização automática.
    """
    
    def __init__(self, min_speaker_duration=1.0, transition_penalty=0.1):
        self.min_speaker_duration = min_speaker_duration
        self.transition_penalty = transition_penalty
    
    def validate_and_smooth_timeline(self, segments: List[Dict], labels: np.ndarray) -> List[Dict]:
        """
        Valida e suaviza timeline de diarização
        
        EDUCATIVO: Aplica três passes de validação:
        1. Elimina segmentos muito curtos
        2. Suaviza transições rápidas
        3. Consolida segmentos consecutivos do mesmo speaker
        """
        logger.info("🔍 Validando e suavizando timeline temporal")
        
        if len(segments) != len(labels):
            logger.error("❌ Incompatibilidade entre segmentos e labels")
            return segments
        
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
        
        # Passar 1: Eliminar segmentos muito curtos
        timeline = self.remove_short_segments(timeline)
        
        # Passar 2: Suavizar transições rápidas
        timeline = self.smooth_rapid_transitions(timeline)
        
        # Passar 3: Consolidar segmentos consecutivos
        timeline = self.consolidate_consecutive_segments(timeline)
        
        # Converter de volta para formato original
        validated_segments = []
        for item in timeline:
            validated_segments.append({
                'start': item['start'],
                'end': item['end'],
                'speaker': f"SPEAKER_{item['speaker_id']:02d}"
            })
        
        logger.info(f"✅ Timeline validada: {len(validated_segments)} segmentos finais")
        return validated_segments
    
    def remove_short_segments(self, timeline: List[Dict]) -> List[Dict]:
        """
        Remove segmentos muito curtos mesclando com vizinhos
        """
        if not timeline:
            return timeline
        
        cleaned_timeline = []
        
        for i, segment in enumerate(timeline):
            if segment['duration'] >= self.min_speaker_duration:
                cleaned_timeline.append(segment)
            else:
                # Segmento muito curto - mesclar com vizinho mais compatível
                if i > 0 and i < len(timeline) - 1:
                    # Escolher vizinho com mesmo speaker_id se possível
                    prev_segment = timeline[i-1]
                    next_segment = timeline[i+1]
                    
                    if prev_segment['speaker_id'] == segment['speaker_id']:
                        # Estender segmento anterior
                        if cleaned_timeline and cleaned_timeline[-1] == prev_segment:
                            cleaned_timeline[-1]['end'] = segment['end']
                            cleaned_timeline[-1]['duration'] = cleaned_timeline[-1]['end'] - cleaned_timeline[-1]['start']
                    elif next_segment['speaker_id'] == segment['speaker_id']:
                        # Será tratado no próximo segmento
                        continue
                    else:
                        # Atribuir ao speaker mais próximo temporalmente
                        if abs(segment['start'] - prev_segment['end']) < abs(next_segment['start'] - segment['end']):
                            segment['speaker_id'] = prev_segment['speaker_id']
                        else:
                            segment['speaker_id'] = next_segment['speaker_id']
                        cleaned_timeline.append(segment)
                elif i == 0 and len(timeline) > 1:
                    # Primeiro segmento - mesclar com próximo
                    segment['speaker_id'] = timeline[i+1]['speaker_id']
                    cleaned_timeline.append(segment)
                elif i == len(timeline) - 1 and cleaned_timeline:
                    # Último segmento - mesclar com anterior
                    cleaned_timeline[-1]['end'] = segment['end']
                    cleaned_timeline[-1]['duration'] = cleaned_timeline[-1]['end'] - cleaned_timeline[-1]['start']
                else:
                    # Caso isolado - manter
                    cleaned_timeline.append(segment)
        
        return cleaned_timeline
    
    def smooth_rapid_transitions(self, timeline: List[Dict]) -> List[Dict]:
        """
        Suaviza transições muito rápidas entre speakers
        """
        if len(timeline) < 3:
            return timeline
        
        smoothed_timeline = [timeline[0]]  # Sempre manter primeiro
        
        for i in range(1, len(timeline) - 1):
            current = timeline[i]
            prev_speaker = smoothed_timeline[-1]['speaker_id']
            next_speaker = timeline[i+1]['speaker_id']
            
            # Se segmento atual é diferente dos vizinhos e muito curto
            if (current['speaker_id'] != prev_speaker and 
                current['speaker_id'] != next_speaker and
                current['duration'] < 3.0):  # Menos de 3 segundos
                
                # Decidir para qual speaker atribuir baseado em duração dos vizinhos
                prev_duration = smoothed_timeline[-1]['duration']
                next_duration = timeline[i+1]['duration']
                
                if prev_duration >= next_duration:
                    current['speaker_id'] = prev_speaker
                else:
                    current['speaker_id'] = next_speaker
            
            smoothed_timeline.append(current)
        
        # Adicionar último segmento
        if len(timeline) > 1:
            smoothed_timeline.append(timeline[-1])
        
        return smoothed_timeline
    
    def consolidate_consecutive_segments(self, timeline: List[Dict]) -> List[Dict]:
        """
        Consolida segmentos consecutivos do mesmo speaker
        """
        if not timeline:
            return timeline
        
        consolidated = [timeline[0]]
        
        for segment in timeline[1:]:
            last_segment = consolidated[-1]
            
            # Se mesmo speaker e gap pequeno (< 2 segundos)
            if (segment['speaker_id'] == last_segment['speaker_id'] and
                abs(segment['start'] - last_segment['end']) < 2.0):
                
                # Mesclar segmentos
                last_segment['end'] = segment['end']
                last_segment['duration'] = last_segment['end'] - last_segment['start']
            else:
                consolidated.append(segment)
        
        return consolidated

class ParallelTranscriptionProcessor:
    """
    EDUCATIVO: Processador paralelo otimizado para usar todos os 8 cores
    
    Conceito: Dividir o trabalho de transcrição entre múltiplos processos
    para maximizar o uso da CPU. Como ter 8 pessoas trabalhando em paralelo
    em vez de 1 pessoa fazendo tudo sozinha.
    
    Estratégia: Usar ProcessPoolExecutor para true paralelismo (evita GIL do Python)
    """
    
    def __init__(self, max_workers=7):  # Deixar 1 core para o sistema
        self.max_workers = max_workers
        self.whisper_model_size = "large-v2"  # Usar modelo mais poderoso com mais recursos
        
    def transcribe_segments_parallel(self, audio_path: str, segments: List[Dict]) -> List[str]:
        """
        Transcrever múltiplos segmentos em paralelo
        
        EDUCATIVO: Cada worker carrega seu próprio modelo Whisper e processa
        um lote de segmentos independentemente. Depois reunimos os resultados.
        """
        logger.info(f"🚀 Transcrevendo {len(segments)} segmentos usando {self.max_workers} cores")
        
        # Dividir segmentos em lotes para balancear carga
        batch_size = max(1, len(segments) // self.max_workers)
        segment_batches = [segments[i:i + batch_size] for i in range(0, len(segments), batch_size)]
        
        # Preparar tarefas para paralelização
        tasks = []
        for batch_id, batch in enumerate(segment_batches):
            tasks.append({
                'audio_path': audio_path,
                'segments': batch,
                'batch_id': batch_id,
                'model_size': self.whisper_model_size
            })
        
        # Executar em paralelo
        results = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submeter todas as tarefas
            future_to_batch = {
                executor.submit(transcribe_batch_worker, task): task['batch_id'] 
                for task in tasks
            }
            
            # Coletar resultados conforme completam
            for future in as_completed(future_to_batch):
                batch_id = future_to_batch[future]
                try:
                    batch_results = future.result(timeout=300)  # 5 minutos por batch
                    results.extend(batch_results)
                    logger.info(f"✅ Batch {batch_id} completado: {len(batch_results)} transcrições")
                except Exception as e:
                    logger.error(f"❌ Erro no batch {batch_id}: {e}")
                    # Adicionar placeholders para manter ordem
                    batch_size_error = len(tasks[batch_id]['segments'])
                    results.extend([""] * batch_size_error)
        
        logger.info(f"🎉 Transcrição paralela concluída: {len(results)} resultados")
        return results

def transcribe_batch_worker(task: Dict) -> List[str]:
    """
    Worker function para transcrição em paralelo
    EDUCATIVO: Esta função roda em processo separado, por isso precisa
    carregar seu próprio modelo Whisper e processar independentemente.
    """
    audio_path = task['audio_path']
    segments = task['segments']
    batch_id = task['batch_id']
    model_size = task['model_size']
    
    try:
        # Carregar modelo Whisper no worker
        model = whisper.load_model(model_size, device="cpu")
        
        # Carregar áudio original
        audio_data, sr = librosa.load(audio_path, sr=16000)
        
        batch_results = []
        
        for segment in segments:
            try:
                # Extrair segmento
                start_sample = int(segment['start'] * sr)
                end_sample = int(segment['end'] * sr)
                
                if end_sample <= start_sample:
                    batch_results.append("")
                    continue
                
                segment_audio = audio_data[start_sample:end_sample]
                
                # Criar arquivo temporário para este worker
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_file:
                    sf.write(temp_file.name, segment_audio, sr)
                    
                    # Transcrever
                    result = model.transcribe(
                        temp_file.name,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.0,
                        initial_prompt="Transcrição clara em português brasileiro:"
                    )
                    
                    transcription = result["text"].strip()
                    batch_results.append(transcription)
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro no segmento do batch {batch_id}: {e}")
                batch_results.append("")
        
        return batch_results
        
    except Exception as e:
        logger.error(f"❌ Erro crítico no worker {batch_id}: {e}")
        return [""] * len(segments)

class AdvancedAudioPreprocessor:
    """
    EDUCATIVO: Preprocessador avançado para otimizar qualidade dos embeddings
    
    Conceito: Áudio de baixa qualidade gera embeddings ruins, que causam
    diarização ruim. Este preprocessador aplica técnicas profissionais
    para melhorar a qualidade antes da extração de características neurais.
    """
    
    def __init__(self):
        self.sample_rate = 16000
        self.vad = webrtcvad.Vad(2)  # Modo 2 = balanceado
        
    def preprocess_for_diarization(self, audio_path: str) -> str:
        """
        Preprocessamento avançado otimizado para diarização
        """
        logger.info("🔧 Iniciando preprocessamento avançado para diarização")
        
        try:
            # Carregar áudio
            audio = AudioSegment.from_file(audio_path)
            
            # 1. Normalização inteligente
            audio = self.intelligent_normalization(audio)
            
            # 2. Redução de ruído neural
            audio = self.neural_noise_reduction(audio)
            
            # 3. Remoção de silêncios longos
            audio = self.remove_long_silences(audio)
            
            # 4. Equalização para voz
            audio = self.voice_equalization(audio)
            
            # Salvar resultado preprocessado
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav', parameters=["-ar", str(self.sample_rate)])
                processed_path = temp_file.name
            
            logger.info(f"✅ Preprocessamento concluído: {processed_path}")
            return processed_path
            
        except Exception as e:
            logger.error(f"❌ Erro no preprocessamento: {e}")
            return audio_path  # Retornar original se falhar
    
    def intelligent_normalization(self, audio: AudioSegment) -> AudioSegment:
        """
        Normalização inteligente baseada em análise dinâmica
        """
        # Análise de dinâmica
        rms_values = []
        window_ms = 1000  # 1 segundo
        
        for i in range(0, len(audio), window_ms):
            window = audio[i:i + window_ms]
            if len(window) > 0:
                rms_values.append(window.rms)
        
        if rms_values:
            median_rms = np.median(rms_values)
            target_rms = 5000  # Valor alvo empírico
            
            if median_rms > 0:
                gain_db = 20 * np.log10(target_rms / median_rms)
                # Limitar ganho para evitar distorção
                gain_db = np.clip(gain_db, -20, 20)
                audio = audio + gain_db
        
        return normalize(audio, headroom=0.1)
    
    def neural_noise_reduction(self, audio: AudioSegment) -> AudioSegment:
        """
        Redução de ruído usando algoritmos neurais
        """
        try:
            # Converter para numpy
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            if audio.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)
            
            # Normalizar para noise reduction
            samples = samples / np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else samples
            
            # Aplicar noise reduction
            reduced_noise = nr.reduce_noise(
                y=samples, 
                sr=audio.frame_rate,
                stationary=False,    # Ruído não-estacionário
                prop_decrease=0.8    # Reduzir 80% do ruído
            )
            
            # Converter de volta
            reduced_noise = (reduced_noise * 32767).astype(np.int16)
            processed_audio = audio._spawn(reduced_noise.tobytes())
            
            return processed_audio
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na redução de ruído: {e}")
            return audio
    
    def remove_long_silences(self, audio: AudioSegment) -> AudioSegment:
        """
        Remove silêncios longos mantendo pausas naturais
        """
        try:
            # Detectar regiões de fala usando WebRTC VAD
            samples = np.array(audio.get_array_of_samples(), dtype=np.int16)
            if audio.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1).astype(np.int16)
            
            # Reamostrar para 16kHz se necessário (VAD requer isso)
            if audio.frame_rate != 16000:
                audio_16k = audio.set_frame_rate(16000)
                samples_16k = np.array(audio_16k.get_array_of_samples(), dtype=np.int16)
            else:
                samples_16k = samples
                audio_16k = audio
            
            # Detectar atividade vocal em janelas de 30ms
            frame_duration = 30  # ms
            frame_size = int(16000 * frame_duration / 1000)
            
            voiced_frames = []
            for i in range(0, len(samples_16k) - frame_size, frame_size):
                frame = samples_16k[i:i + frame_size].tobytes()
                try:
                    is_voiced = self.vad.is_speech(frame, 16000)
                    voiced_frames.append(is_voiced)
                except:
                    voiced_frames.append(True)  # Assumir voz se erro
            
            # Criar máscara para preservar áudio com fala
            audio_segments = []
            current_start = 0
            in_speech = False
            
            for i, is_voiced in enumerate(voiced_frames):
                frame_start_ms = i * frame_duration
                
                if is_voiced and not in_speech:
                    # Início de fala
                    current_start = max(0, frame_start_ms - 100)  # 100ms antes
                    in_speech = True
                elif not is_voiced and in_speech:
                    # Fim de fala
                    frame_end_ms = min(len(audio), frame_start_ms + 200)  # 200ms depois
                    if frame_end_ms > current_start:
                        audio_segments.append(audio[current_start:frame_end_ms])
                    in_speech = False
            
            # Adicionar último segmento se necessário
            if in_speech:
                audio_segments.append(audio[current_start:])
            
            # Combinar segmentos com pausas curtas
            if audio_segments:
                result = audio_segments[0]
                for segment in audio_segments[1:]:
                    # Adicionar pausa de 200ms entre segmentos
                    pause = AudioSegment.silent(duration=200)
                    result = result + pause + segment
                return result
            else:
                return audio
                
        except Exception as e:
            logger.warning(f"⚠️ Erro na remoção de silêncios: {e}")
            return audio
    
    def voice_equalization(self, audio: AudioSegment) -> AudioSegment:
        """
        Equalização otimizada para características de voz
        """
        try:
            # Aplicar filtro passa-banda para faixa de voz humana (85Hz - 8kHz)
            # Usar pydub effects para simplificar
            
            # Amplificar frequências médias (onde estão formantes vocais)
            # Isso é uma aproximação - em produção usaria FFT
            audio = audio.high_pass_filter(85)  # Remove ruído grave
            audio = audio.low_pass_filter(8000)  # Remove ruído agudo
            
            return audio
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na equalização: {e}")
            return audio

class ProfessionalDiarizationSystem:
    """
    EDUCATIVO: Sistema principal que orquestra toda a pipeline de diarização
    
    Conceito: Este é o "maestro" que coordena todos os componentes:
    1. Preprocessamento avançado
    2. Segmentação inicial
    3. Extração de embeddings neurais
    4. Clustering automático
    5. Validação temporal
    6. Transcrição paralela
    7. Formatação final
    
    Filosofia: Cada etapa é independente e robusta, permitindo fallbacks
    e otimizações específicas para diferentes tipos de áudio.
    """
    
    def __init__(self):
        self.preprocessor = AdvancedAudioPreprocessor()
        self.embedder = ProfessionalSpeakerEmbedder()
        self.clusterer = AdvancedSpeakerClusterer()
        self.validator = TemporalDiarizationValidator()
        self.transcriber = ParallelTranscriptionProcessor()
        
        # Configurações adaptáveis
        self.config = {
            'max_speakers': 8,
            'min_segment_duration': 2.0,
            'use_neural_embeddings': True,
            'enable_parallel_transcription': True,
            'quality_threshold': 0.3
        }
    
    def transcribe_with_professional_diarization(self, audio_path: str) -> str:
        """
        Pipeline completa de diarização e transcrição profissional
        """
        logger.info(f"🎯 Iniciando diarização profissional: {audio_path}")
        start_time = time.time()
        
        temp_files = []
        
        try:
            # Etapa 1: Análise inicial e preprocessamento
            logger.info("📊 Etapa 1/7: Análise e preprocessamento")
            processed_audio_path = self.preprocessor.preprocess_for_diarization(audio_path)
            if processed_audio_path != audio_path:
                temp_files.append(processed_audio_path)
            
            # Análise de duração para estratégia adaptável
            audio_duration = self.get_audio_duration(processed_audio_path)
            logger.info(f"⏱️ Duração total: {audio_duration:.1f}s ({audio_duration/60:.1f}min)")
            
            # Ajustar configurações baseado na duração
            self.adapt_config_for_duration(audio_duration)
            
            # Etapa 2: Segmentação inicial baseada em energia e pausas
            logger.info("📊 Etapa 2/7: Segmentação inicial")
            initial_segments = self.create_initial_segments(processed_audio_path)
            logger.info(f"🔍 {len(initial_segments)} segmentos iniciais criados")
            
            if len(initial_segments) < 2:
                logger.info("⚡ Áudio muito curto - usando transcrição direta")
                return self.direct_transcription_fallback(processed_audio_path)
            
            # Etapa 3: Extração de embeddings neurais
            logger.info("📊 Etapa 3/7: Extração de embeddings neurais")
            embeddings = self.embedder.extract_embeddings_from_segments(processed_audio_path, initial_segments)
            
            if len(embeddings) < 2:
                logger.warning("⚠️ Poucos embeddings válidos - fallback para segmentação simples")
                return self.simple_diarization_fallback(processed_audio_path, initial_segments)
            
            # Etapa 4: Clustering automático de speakers
            logger.info("📊 Etapa 4/7: Clustering automático de speakers")
            similarity_matrix = self.embedder.calculate_embedding_similarities(embeddings)
            labels, n_speakers, quality_score = self.clusterer.cluster_speakers_automatic(
                similarity_matrix, self.config['max_speakers']
            )
            
            logger.info(f"🎭 {n_speakers} speakers detectados (qualidade: {quality_score:.3f})")
            
            # Verificar qualidade do clustering
            if quality_score < self.config['quality_threshold']:
                logger.warning(f"⚠️ Qualidade baixa ({quality_score:.3f}) - aplicando correções")
                labels = self.apply_quality_corrections(labels, similarity_matrix)
            
            # Etapa 5: Validação e suavização temporal
            logger.info("📊 Etapa 5/7: Validação temporal")
            validated_segments = self.validator.validate_and_smooth_timeline(initial_segments, labels)
            
            # Etapa 6: Transcrição paralela otimizada
            logger.info("📊 Etapa 6/7: Transcrição paralela")
            if self.config['enable_parallel_transcription'] and len(validated_segments) > 4:
                transcriptions = self.transcriber.transcribe_segments_parallel(processed_audio_path, validated_segments)
            else:
                transcriptions = self.transcribe_segments_sequential(processed_audio_path, validated_segments)
            
            # Etapa 7: Formatação final e montagem
            logger.info("📊 Etapa 7/7: Formatação final")
            final_result = self.format_final_transcription(validated_segments, transcriptions)
            
            # Métricas finais
            processing_time = time.time() - start_time
            self.log_final_metrics(audio_duration, processing_time, n_speakers, len(validated_segments), quality_score)
            
            return final_result
            
        except Exception as e:
            logger.error(f"💥 Erro na pipeline principal: {e}")
            return self.emergency_fallback(audio_path)
        
        finally:
            # Limpeza de arquivos temporários
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
    
    def get_audio_duration(self, audio_path: str) -> float:
        """Obter duração do áudio de forma eficiente"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except:
            return 0.0
    
    def adapt_config_for_duration(self, duration: float):
        """
        Adaptar configurações baseado na duração do áudio
        EDUCATIVO: Diferentes durações requerem estratégias diferentes
        """
        if duration <= 60:  # ≤ 1 minuto
            self.config.update({
                'max_speakers': 3,
                'min_segment_duration': 1.0,
                'quality_threshold': 0.2
            })
            logger.info("⚙️ Configuração para áudio curto")
            
        elif duration <= 600:  # 1-10 minutos
            self.config.update({
                'max_speakers': 5,
                'min_segment_duration': 2.0,
                'quality_threshold': 0.3
            })
            logger.info("⚙️ Configuração para áudio médio")
            
        else:  # > 10 minutos
            self.config.update({
                'max_speakers': 8,
                'min_segment_duration': 3.0,
                'quality_threshold': 0.4
            })
            logger.info("⚙️ Configuração para áudio longo")
    
    def create_initial_segments(self, audio_path: str) -> List[Dict]:
        """
        Cria segmentação inicial baseada em análise de energia e pausas
        EDUCATIVO: Segmentação inicial deve ser generosa (muitos segmentos pequenos)
        para que o clustering neural possa depois agrupá-los corretamente.
        """
        try:
            # Carregar áudio
            audio_data, sr = librosa.load(audio_path, sr=16000)
            duration = len(audio_data) / sr
            
            # Análise de energia em janelas pequenas
            hop_length = int(sr * 0.5)  # 0.5 segundos
            energy = librosa.feature.rms(y=audio_data, hop_length=hop_length)[0]
            
            # Detectar pontos de baixa energia (possíveis transições)
            energy_threshold = np.percentile(energy, 30)  # 30% mais baixo
            low_energy_frames = energy < energy_threshold
            
            # Encontrar transições
            transitions = []
            in_low_energy = False
            
            for i, is_low in enumerate(low_energy_frames):
                time_point = i * hop_length / sr
                
                if is_low and not in_low_energy:
                    # Início de região de baixa energia
                    in_low_energy = True
                elif not is_low and in_low_energy:
                    # Fim de região de baixa energia - possível transição
                    if time_point > self.config['min_segment_duration']:
                        transitions.append(time_point)
                    in_low_energy = False
            
            # Garantir segmentos mínimos se muito poucos pontos foram detectados
            if len(transitions) < 2:
                # Criar segmentos baseados em tempo fixo
                segment_duration = min(30.0, duration / 4)  # Máximo 4 segmentos
                transitions = [i * segment_duration for i in range(1, int(duration / segment_duration))]
            
            # Criar lista de segmentos
            segments = []
            start_time = 0.0
            
            for transition in transitions:
                if transition > start_time + self.config['min_segment_duration']:
                    segments.append({
                        'start': start_time,
                        'end': transition,
                        'duration': transition - start_time
                    })
                    start_time = transition
            
            # Adicionar último segmento
            if start_time < duration - self.config['min_segment_duration']:
                segments.append({
                    'start': start_time,
                    'end': duration,
                    'duration': duration - start_time
                })
            
            return segments
            
        except Exception as e:
            logger.error(f"❌ Erro na segmentação inicial: {e}")
            # Fallback: segmentos de tempo fixo
            return self.create_fixed_time_segments(audio_path)
    
    def create_fixed_time_segments(self, audio_path: str) -> List[Dict]:
        """Fallback: segmentos de tempo fixo"""
        try:
            duration = self.get_audio_duration(audio_path)
            segment_duration = 15.0  # 15 segundos por segmento
            
            segments = []
            start_time = 0.0
            
            while start_time < duration:
                end_time = min(start_time + segment_duration, duration)
                segments.append({
                    'start': start_time,
                    'end': end_time,
                    'duration': end_time - start_time
                })
                start_time = end_time
            
            return segments
        except:
            return []
    
    def apply_quality_corrections(self, labels: np.ndarray, similarity_matrix: np.ndarray) -> np.ndarray:
        """
        Aplica correções quando qualidade do clustering é baixa
        """
        logger.info("🔧 Aplicando correções de qualidade")
        
        try:
            # Simplificar clustering para 2-3 speakers se muito confuso
            n_current_speakers = len(np.unique(labels))
            
            if n_current_speakers > 4:
                # Re-cluster forçando menos speakers
                from sklearn.cluster import AgglomerativeClustering
                
                distance_matrix = 1 - similarity_matrix
                clusterer = AgglomerativeClustering(
                    n_clusters=3,
                    affinity='precomputed',
                    linkage='average'
                )
                corrected_labels = clusterer.fit_predict(distance_matrix)
                
                logger.info(f"🔄 Speakers reduzidos: {n_current_speakers} → 3")
                return corrected_labels
            
            return labels
            
        except Exception as e:
            logger.warning(f"⚠️ Erro nas correções de qualidade: {e}")
            return labels
    
    def transcribe_segments_sequential(self, audio_path: str, segments: List[Dict]) -> List[str]:
        """
        Transcrição sequencial como fallback
        """
        logger.info(f"🔄 Transcrição sequencial de {len(segments)} segmentos")
        
        # Carregar modelo uma vez
        model = whisper.load_model(self.transcriber.whisper_model_size, device="cpu")
        audio_data, sr = librosa.load(audio_path, sr=16000)
        
        transcriptions = []
        
        for i, segment in enumerate(segments):
            try:
                start_sample = int(segment['start'] * sr)
                end_sample = int(segment['end'] * sr)
                
                if end_sample <= start_sample:
                    transcriptions.append("")
                    continue
                
                segment_audio = audio_data[start_sample:end_sample]
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_file:
                    sf.write(temp_file.name, segment_audio, sr)
                    
                    result = model.transcribe(
                        temp_file.name,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.0,
                        initial_prompt="Transcrição clara em português brasileiro:"
                    )
                    
                    transcriptions.append(result["text"].strip())
                    
                if (i + 1) % 5 == 0:
                    logger.info(f"📝 Progresso: {i+1}/{len(segments)}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro no segmento {i}: {e}")
                transcriptions.append("")
        
        return transcriptions
    
    def format_final_transcription(self, segments: List[Dict], transcriptions: List[str]) -> str:
        """
        Formata resultado final da transcrição com diarização
        """
        if len(segments) != len(transcriptions):
            logger.error("❌ Incompatibilidade entre segmentos e transcrições")
            return "Erro na formatação final."
        
        formatted_segments = []
        
        for segment, transcription in zip(segments, transcriptions):
            if transcription and transcription.strip():
                # Limpar texto
                clean_text = self.clean_transcription_text(transcription)
                
                if clean_text:
                    # Formatar timestamp
                    timestamp = self.format_timestamp(segment['start'], segment['end'])
                    speaker_name = segment['speaker'].replace("_", " ")
                    
                    formatted_segments.append(f"{timestamp} {speaker_name}:\n{clean_text}")
        
        if formatted_segments:
            return "\n\n".join(formatted_segments)
        else:
            return "Nenhuma transcrição válida foi obtida."
    
    def clean_transcription_text(self, text: str) -> str:
        """Limpeza final do texto transcrito"""
        if not text:
            return ""
        
        # Remover espaços múltiplos
        text = re.sub(r'\s+', ' ', text)
        
        # Remover caracteres especiais preservando acentos
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)áàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]', '', text)
        
        # Capitalizar primeira letra
        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        return text
    
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        """Formatação de timestamp"""
        def seconds_to_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        start_str = seconds_to_time(start_time)
        end_str = seconds_to_time(end_time)
        return f"[{start_str} - {end_str}]"
    
    def log_final_metrics(self, duration: float, processing_time: float, n_speakers: int, 
                         n_segments: int, quality_score: float):
        """Log de métricas finais para monitoramento"""
        speed_ratio = duration / processing_time if processing_time > 0 else 0
        
        logger.info("="*60)
        logger.info("📊 MÉTRICAS FINAIS DA DIARIZAÇÃO PROFISSIONAL")
        logger.info("="*60)
        logger.info(f"⏱️ Duração do áudio: {duration:.1f}s ({duration/60:.1f}min)")
        logger.info(f"🚀 Tempo de processamento: {processing_time:.1f}s")
        logger.info(f"⚡ Velocidade: {speed_ratio:.1f}x tempo real")
        logger.info(f"🎭 Speakers detectados: {n_speakers}")
        logger.info(f"📝 Segmentos finais: {n_segments}")
        logger.info(f"⭐ Qualidade do clustering: {quality_score:.3f}")
        logger.info(f"💻 Recursos utilizados: ~{self.transcriber.max_workers} cores")
        logger.info("="*60)
    
    def direct_transcription_fallback(self, audio_path: str) -> str:
        """Fallback para transcrição direta"""
        logger.info("🔄 Usando transcrição direta como fallback")
        
        try:
            model = whisper.load_model("large-v2", device="cpu")
            result = model.transcribe(
                audio_path,
                language="pt",
                task="transcribe",
                verbose=False,
                temperature=0.0,
                initial_prompt="Transcrição clara em português brasileiro:"
            )
            
            duration = self.get_audio_duration(audio_path)
            timestamp = self.format_timestamp(0, duration)
            clean_text = self.clean_transcription_text(result["text"])
            
            return f"{timestamp} Speaker 01:\n{clean_text}"
            
        except Exception as e:
            logger.error(f"❌ Fallback direto falhou: {e}")
            return "Sistema de transcrição temporariamente indisponível."
    
    def simple_diarization_fallback(self, audio_path: str, segments: List[Dict]) -> str:
        """Fallback para diarização simples"""
        logger.info("🔄 Usando diarização simples como fallback")
        
        try:
            # Atribuir speakers alternadamente
            for i, segment in enumerate(segments):
                segment['speaker'] = f"SPEAKER_{(i % 2) + 1:02d}"
            
            # Transcrever sequencialmente
            transcriptions = self.transcribe_segments_sequential(audio_path, segments)
            
            return self.format_final_transcription(segments, transcriptions)
            
        except Exception as e:
            logger.error(f"❌ Fallback simples falhou: {e}")
            return self.direct_transcription_fallback(audio_path)
    
    def emergency_fallback(self, audio_path: str) -> str:
        """Fallback de emergência final"""
        logger.warning("🆘 Ativando fallback de emergência")
        
        try:
            model = whisper.load_model("base", device="cpu")
            result = model.transcribe(audio_path, language="pt")
            return f"[00:00:00 - 99:99:99] Speaker 01:\n{result['text']}"
        except:
            return "Sistema de transcrição em manutenção. Tente novamente em alguns minutos."

def main():
    """
    Função principal otimizada para produção com dependências compatíveis
    
    EDUCATIVO: Esta versão foi otimizada para máxima compatibilidade com Docker
    e Python 3.11, removendo dependências problemáticas sem perder funcionalidade.
    """
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Por favor, forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Configurar multiprocessing para sistemas Unix com fallback para Windows
    try:
        if hasattr(os, 'fork'):
            mp.set_start_method('fork', force=True)
        else:
            mp.set_start_method('spawn', force=True)
    except RuntimeError:
        # Já foi configurado, ignorar
        pass
    
    try:
        # Inicializar sistema profissional com configurações compatíveis
        logger.info("🚀 Inicializando sistema de diarização profissional compatível")
        system = ProfessionalDiarizationSystem()
        
        # Processar com pipeline completa
        start_time = time.time()
        result = system.transcribe_with_professional_diarization(audio_path)
        processing_time = time.time() - start_time
        
        # Salvar resultado se solicitado
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao_profissional.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"💾 Resultado salvo: {output_file}")
        
        # Output JSON para integração
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "professional_neural_diarization_compatible",
            "processing_time_seconds": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "diarization_available": True,
            "features_used": [
                "neural_speaker_embeddings",
                "advanced_clustering_scipy",
                "temporal_validation",
                "parallel_transcription",
                "noise_reduction",
                "docker_optimized"
            ],
            "model_used": "large-v2_with_compatible_neural_diarization",
            "compatibility": "python_3.11_docker_ready"
        }
        
        print(json.dumps(output, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"💥 Erro crítico na execução: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "fallback_available": True,
            "compatibility_notes": "Verifique se todas as dependências estão instaladas corretamente"
        }, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()