"""
Pipeline de Diarização
Usa pyannote.audio para diarização de speakers
Processa audio em chunks alinhados com o Whisper
Identifica número de speakers automaticamente
Mantém consistência de speaker_id entre chunks
"""

import numpy as np
import torch
import time
import threading
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import structlog
import json
from pathlib import Path
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import librosa
import soundfile as sf

logger = structlog.get_logger()

@dataclass
class SpeakerSegment:
    """Segmento de fala de um speaker"""
    speaker_id: str
    start_time: float
    end_time: float
    confidence: float
    chunk_id: str
    global_start_time: float
    global_end_time: float

@dataclass
class DiarizationResult:
    """Resultado da diarização"""
    chunk_id: str
    start_time: float
    end_time: float
    speakers: List[str]
    segments: List[SpeakerSegment]
    num_speakers: int
    processing_time: float
    error: Optional[str] = None

@dataclass
class DiarizationConfig:
    """Configuração da diarização"""
    max_speakers: int = 8
    min_speaker_duration: float = 1.0  # segundos
    overlap_threshold: float = 0.5  # para resolver sobreposições
    confidence_threshold: float = 0.5
    use_auth_token: bool = False
    auth_token: Optional[str] = None
    model_name: str = "pyannote/speaker-diarization-3.1"
    clustering_method: str = "centroid"
    embedding_model: str = "speechbrain/spkrec-ecapa-voxceleb"
    device: str = "cpu"

class SpeakerDiarizer:
    """
    Sistema de diarização de speakers usando pyannote.audio
    """
    
    def __init__(self, config: Optional[DiarizationConfig] = None):
        self.config = config or DiarizationConfig()
        self.pipeline = None
        self.pipeline_lock = threading.Lock()
        self.speaker_embeddings = {}
        self.embedding_lock = threading.Lock()
        self.speaker_mapping = {}  # Mapeamento entre chunks
        self.mapping_lock = threading.Lock()
        
        self.processing_stats = {
            "total_chunks_processed": 0,
            "successful_diarizations": 0,
            "failed_diarizations": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "total_speakers_detected": 0,
            "total_segments": 0
        }
        
        logger.info("SpeakerDiarizer inicializado",
                   max_speakers=self.config.max_speakers,
                   model=self.config.model_name,
                   device=self.config.device)
    
    def _load_pipeline(self):
        """Carrega pipeline de diarização (thread-safe)"""
        with self.pipeline_lock:
            if self.pipeline is None:
                logger.info("Carregando pipeline de diarização", model=self.config.model_name)
                
                try:
                    from pyannote.audio import Pipeline
                    
                    # Configurar token se necessário
                    if self.config.use_auth_token and self.config.auth_token:
                        auth_token = self.config.auth_token
                    else:
                        auth_token = None
                    
                    # Carregar pipeline
                    self.pipeline = Pipeline.from_pretrained(
                        self.config.model_name,
                        use_auth_token=auth_token
                    )
                    
                    # Configurar device
                    if self.config.device == "cuda" and torch.cuda.is_available():
                        self.pipeline.to(torch.device("cuda"))
                    else:
                        self.pipeline.to(torch.device("cpu"))
                    
                    logger.info("Pipeline de diarização carregado com sucesso",
                               model=self.config.model_name,
                               device=self.config.device)
                    
                except Exception as e:
                    logger.error("Erro ao carregar pipeline de diarização", error=str(e))
                    raise
    
    def _preprocess_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Pré-processa áudio para diarização"""
        try:
            # pyannote espera 16kHz
            if sample_rate != 16000:
                audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=16000)
            
            # Normalizar
            if np.max(np.abs(audio_data)) > 1.0:
                audio_data = audio_data / np.max(np.abs(audio_data))
            
            # Verificar se não está vazio
            if len(audio_data) == 0:
                raise ValueError("Áudio vazio após pré-processamento")
            
            return audio_data
            
        except Exception as e:
            logger.error("Erro no pré-processamento", error=str(e))
            raise
    
    def _save_audio_temp(self, audio_data: np.ndarray, sample_rate: int) -> str:
        """Salva áudio em arquivo temporário"""
        try:
            # Criar arquivo temporário
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # Salvar áudio
            sf.write(temp_path, audio_data, sample_rate)
            
            return temp_path
            
        except Exception as e:
            logger.error("Erro ao salvar áudio temporário", error=str(e))
            raise
    
    def _extract_speaker_embeddings(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, np.ndarray]:
        """Extrai embeddings dos speakers"""
        try:
            from speechbrain.pretrained import EncoderClassifier
            
            # Carregar modelo de embedding
            embedding_model = EncoderClassifier.from_hparams(
                source=self.config.embedding_model,
                savedir="pretrained_models/spkrec-ecapa-voxceleb"
            )
            
            # Processar áudio em chunks para extrair embeddings
            chunk_duration = 3.0  # 3 segundos por chunk
            chunk_size = int(sample_rate * chunk_duration)
            
            embeddings = {}
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                
                if len(chunk) < sample_rate:  # Mínimo 1 segundo
                    continue
                
                # Extrair embedding
                with torch.no_grad():
                    embedding = embedding_model.encode_batch(torch.tensor(chunk).unsqueeze(0))
                    embedding = embedding.squeeze().cpu().numpy()
                
                embeddings[f"chunk_{i}"] = embedding
            
            return embeddings
            
        except Exception as e:
            logger.error("Erro na extração de embeddings", error=str(e))
            return {}
    
    def _map_speakers_between_chunks(self, current_speakers: List[str], 
                                   previous_speakers: List[str]) -> Dict[str, str]:
        """Mapeia speakers entre chunks usando similaridade de embedding"""
        if not previous_speakers:
            return {speaker: speaker for speaker in current_speakers}
        
        try:
            # Calcular similaridade entre embeddings
            mapping = {}
            used_previous = set()
            
            for current_speaker in current_speakers:
                best_match = None
                best_similarity = -1
                
                for previous_speaker in previous_speakers:
                    if previous_speaker in used_previous:
                        continue
                    
                    # Calcular similaridade (cosine similarity)
                    if (current_speaker in self.speaker_embeddings and 
                        previous_speaker in self.speaker_embeddings):
                        
                        current_emb = self.speaker_embeddings[current_speaker]
                        previous_emb = self.speaker_embeddings[previous_speaker]
                        
                        similarity = np.dot(current_emb, previous_emb) / (
                            np.linalg.norm(current_emb) * np.linalg.norm(previous_emb)
                        )
                        
                        if similarity > best_similarity and similarity > 0.7:  # Threshold
                            best_similarity = similarity
                            best_match = previous_speaker
                
                if best_match:
                    mapping[current_speaker] = best_match
                    used_previous.add(best_match)
                else:
                    # Speaker novo
                    mapping[current_speaker] = current_speaker
            
            return mapping
            
        except Exception as e:
            logger.error("Erro no mapeamento de speakers", error=str(e))
            return {speaker: speaker for speaker in current_speakers}
    
    def diarize_chunk(self, chunk_id: str, audio_data: np.ndarray, 
                     sample_rate: int, start_time: float, end_time: float,
                     progress_callback: Optional[Callable] = None) -> DiarizationResult:
        """
        Diariza um chunk individual
        """
        start_processing = time.time()
        
        try:
            # Carregar pipeline se necessário
            self._load_pipeline()
            
            # Pré-processar áudio
            processed_audio = self._preprocess_audio(audio_data, sample_rate)
            
            # Salvar em arquivo temporário
            temp_path = self._save_audio_temp(processed_audio, sample_rate)
            
            try:
                # Executar diarização
                logger.debug("Iniciando diarização", chunk_id=chunk_id)
                
                diarization = self.pipeline(temp_path)
                
                # Processar resultado
                segments = []
                speakers = set()
                
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    # Filtrar por duração mínima
                    if turn.end - turn.start < self.config.min_speaker_duration:
                        continue
                    
                    # Filtrar por confiança
                    if hasattr(turn, 'confidence') and turn.confidence < self.config.confidence_threshold:
                        continue
                    
                    # Criar segmento
                    segment = SpeakerSegment(
                        speaker_id=speaker,
                        start_time=turn.start,
                        end_time=turn.end,
                        confidence=getattr(turn, 'confidence', 1.0),
                        chunk_id=chunk_id,
                        global_start_time=start_time + turn.start,
                        global_end_time=start_time + turn.end
                    )
                    
                    segments.append(segment)
                    speakers.add(speaker)
                
                # Limitar número de speakers
                if len(speakers) > self.config.max_speakers:
                    logger.warning(f"Demasiados speakers detectados: {len(speakers)} > {self.config.max_speakers}")
                    # Manter apenas os speakers com mais tempo de fala
                    speaker_durations = {}
                    for segment in segments:
                        duration = segment.end_time - segment.start_time
                        speaker_durations[segment.speaker_id] = speaker_durations.get(segment.speaker_id, 0) + duration
                    
                    # Ordenar por duração e manter apenas os top speakers
                    top_speakers = sorted(speaker_durations.items(), key=lambda x: x[1], reverse=True)[:self.config.max_speakers]
                    top_speaker_ids = {speaker for speaker, _ in top_speakers}
                    
                    segments = [s for s in segments if s.speaker_id in top_speaker_ids]
                    speakers = top_speaker_ids
                
                # Mapear speakers com chunks anteriores
                with self.mapping_lock:
                    previous_speakers = list(self.speaker_mapping.keys())
                    speaker_mapping = self._map_speakers_between_chunks(list(speakers), previous_speakers)
                    
                    # Atualizar mapeamento global
                    for current_speaker, mapped_speaker in speaker_mapping.items():
                        self.speaker_mapping[mapped_speaker] = mapped_speaker
                    
                    # Aplicar mapeamento aos segmentos
                    for segment in segments:
                        if segment.speaker_id in speaker_mapping:
                            segment.speaker_id = speaker_mapping[segment.speaker_id]
                
                processing_time = time.time() - start_processing
                
                result = DiarizationResult(
                    chunk_id=chunk_id,
                    start_time=start_time,
                    end_time=end_time,
                    speakers=list(speakers),
                    segments=segments,
                    num_speakers=len(speakers),
                    processing_time=processing_time
                )
                
                # Atualizar estatísticas
                self.processing_stats["total_chunks_processed"] += 1
                self.processing_stats["successful_diarizations"] += 1
                self.processing_stats["total_processing_time"] += processing_time
                self.processing_stats["total_speakers_detected"] += len(speakers)
                self.processing_stats["total_segments"] += len(segments)
                self.processing_stats["average_processing_time"] = (
                    self.processing_stats["total_processing_time"] / 
                    self.processing_stats["successful_diarizations"]
                )
                
                logger.info("Diarização concluída",
                           chunk_id=chunk_id,
                           num_speakers=len(speakers),
                           num_segments=len(segments),
                           processing_time=f"{processing_time:.2f}s")
                
                return result
                
            finally:
                # Limpar arquivo temporário
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            processing_time = time.time() - start_processing
            error_msg = f"Erro na diarização: {str(e)}"
            
            logger.error("Erro na diarização",
                        chunk_id=chunk_id,
                        error=str(e),
                        processing_time=f"{processing_time:.2f}s")
            
            # Atualizar estatísticas
            self.processing_stats["total_chunks_processed"] += 1
            self.processing_stats["failed_diarizations"] += 1
            
            return DiarizationResult(
                chunk_id=chunk_id,
                start_time=start_time,
                end_time=end_time,
                speakers=[],
                segments=[],
                num_speakers=0,
                processing_time=processing_time,
                error=error_msg
            )
    
    def diarize_batch(self, chunks: List[Tuple[str, np.ndarray, int, float, float]],
                     max_workers: Optional[int] = None,
                     progress_callback: Optional[Callable] = None) -> List[DiarizationResult]:
        """
        Diariza múltiplos chunks em paralelo
        """
        if not chunks:
            return []
        
        logger.info("Iniciando diarização em lote",
                   total_chunks=len(chunks))
        
        results = []
        
        # Usar ThreadPoolExecutor para processamento paralelo
        max_workers = max_workers or min(2, len(chunks))  # Limitar a 2 workers para diarização
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter jobs
            future_to_chunk = {}
            
            for chunk_id, audio_data, sample_rate, start_time, end_time in chunks:
                future = executor.submit(
                    self.diarize_chunk,
                    chunk_id, audio_data, sample_rate, start_time, end_time
                )
                future_to_chunk[future] = chunk_id
            
            # Coletar resultados
            completed = 0
            for future in as_completed(future_to_chunk):
                chunk_id = future_to_chunk[future]
                completed += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Callback de progresso
                    if progress_callback:
                        progress_callback(completed, len(chunks), result)
                    
                    logger.debug("Chunk diarizado",
                               chunk_id=chunk_id,
                               completed=f"{completed}/{len(chunks)}")
                    
                except Exception as e:
                    logger.error("Erro no processamento do chunk",
                               chunk_id=chunk_id,
                               error=str(e))
                    
                    # Criar resultado de erro
                    error_result = DiarizationResult(
                        chunk_id=chunk_id,
                        start_time=0.0,
                        end_time=0.0,
                        speakers=[],
                        segments=[],
                        num_speakers=0,
                        processing_time=0.0,
                        error=f"Erro no executor: {str(e)}"
                    )
                    results.append(error_result)
        
        # Ordenar resultados por chunk_id
        results.sort(key=lambda x: x.chunk_id)
        
        logger.info("Diarização em lote concluída",
                   total_chunks=len(chunks),
                   successful=len([r for r in results if not r.error]),
                   failed=len([r for r in results if r.error]))
        
        return results
    
    def process_audio_chunks(self, chunks: List[Any],  # List[AudioChunk]
                           progress_callback: Optional[Callable] = None) -> List[DiarizationResult]:
        """
        Processa lista de AudioChunk e retorna resultados
        """
        # Converter AudioChunk para formato esperado
        chunk_data = []
        for chunk in chunks:
            chunk_data.append((
                chunk.chunk_id,
                chunk.audio_data,
                chunk.sample_rate,
                chunk.start_time,
                chunk.end_time
            ))
        
        return self.diarize_batch(chunk_data, progress_callback=progress_callback)
    
    def get_speaker_statistics(self, results: List[DiarizationResult]) -> Dict[str, Any]:
        """Retorna estatísticas dos speakers"""
        if not results:
            return {}
        
        all_speakers = set()
        speaker_durations = {}
        total_segments = 0
        
        for result in results:
            for segment in result.segments:
                all_speakers.add(segment.speaker_id)
                duration = segment.end_time - segment.start_time
                speaker_durations[segment.speaker_id] = speaker_durations.get(segment.speaker_id, 0) + duration
                total_segments += 1
        
        return {
            "total_speakers": len(all_speakers),
            "total_segments": total_segments,
            "speaker_durations": speaker_durations,
            "avg_segments_per_speaker": total_segments / len(all_speakers) if all_speakers else 0,
            "most_active_speaker": max(speaker_durations.items(), key=lambda x: x[1])[0] if speaker_durations else None
        }
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de processamento"""
        return self.processing_stats.copy()
    
    def save_results(self, results: List[DiarizationResult], output_path: str):
        """Salva resultados em arquivo JSON"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Converter para formato serializável
            serializable_results = []
            for result in results:
                serializable_results.append({
                    "chunk_id": result.chunk_id,
                    "start_time": result.start_time,
                    "end_time": result.end_time,
                    "speakers": result.speakers,
                    "num_speakers": result.num_speakers,
                    "processing_time": result.processing_time,
                    "error": result.error,
                    "segments": [
                        {
                            "speaker_id": segment.speaker_id,
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "confidence": segment.confidence,
                            "global_start_time": segment.global_start_time,
                            "global_end_time": segment.global_end_time
                        }
                        for segment in result.segments
                    ]
                })
            
            # Salvar arquivo
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_results, f, indent=2, ensure_ascii=False)
            
            logger.info("Resultados salvos", output_path=str(output_path))
            
        except Exception as e:
            logger.error("Erro ao salvar resultados", error=str(e))
            raise
    
    def cleanup(self):
        """Limpeza de recursos"""
        logger.info("Limpando recursos do SpeakerDiarizer")
        
        # Liberar pipeline da memória
        with self.pipeline_lock:
            if self.pipeline is not None:
                del self.pipeline
                self.pipeline = None
        
        # Limpar embeddings
        with self.embedding_lock:
            self.speaker_embeddings.clear()
        
        # Limpar mapeamento
        with self.mapping_lock:
            self.speaker_mapping.clear()
        
        # Forçar garbage collection
        import gc
        gc.collect()
        
        logger.info("Recursos limpos")

# Função utilitária para diarização simples
def diarize_audio_file(file_path: str, output_path: Optional[str] = None) -> DiarizationResult:
    """
    Função utilitária para diarização de arquivo único
    """
    # Carregar áudio
    audio_data, sample_rate = librosa.load(file_path, sr=16000)
    
    # Configurar diarizer
    config = DiarizationConfig()
    diarizer = SpeakerDiarizer(config)
    
    # Diarizar
    result = diarizer.diarize_chunk(
        "single_file",
        audio_data,
        sample_rate,
        0.0,
        len(audio_data) / sample_rate
    )
    
    # Salvar se output_path especificado
    if output_path:
        diarizer.save_results([result], output_path)
    
    # Limpeza
    diarizer.cleanup()
    
    return result 