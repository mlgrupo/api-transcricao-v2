"""
Pipeline Whisper Otimizado
Carrega modelo whisper-large apenas uma vez na memória
Processa chunks em batch quando possível
Implementa retry automático para chunks que falharem
Mantém timestamps precisos mesmo com chunking
"""

import whisper
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
import hashlib

# Importar faster-whisper para turbo mode
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger = structlog.get_logger()
    logger.warning("faster-whisper não disponível, usando whisper padrão")

logger = structlog.get_logger()

@dataclass
class WhisperResult:
    """Resultado da transcrição Whisper"""
    chunk_id: str
    start_time: float
    end_time: float
    text: str
    language: str
    confidence: float
    segments: List[Dict[str, Any]]
    processing_time: float
    model_used: str
    error: Optional[str] = None

@dataclass
class WhisperConfig:
    """Configuração do Whisper"""
    model_name: str = "large-v3"
    temperature: float = 0.0
    batch_size: int = 4
    max_retries: int = 3
    timeout_per_chunk: int = 600  # 10 minutos
    device: str = "cpu"
    compute_type: str = "float16"
    language: Optional[str] = None
    task: str = "transcribe"
    word_timestamps: bool = True
    condition_on_previous_text: bool = True
    initial_prompt: Optional[str] = None

class WhisperProcessor:
    """
    Processador Whisper otimizado para processamento em lote
    """
    
    def __init__(self, config: Optional[WhisperConfig] = None):
        self.config = config or WhisperConfig()
        self.model = None
        self.model_lock = threading.Lock()
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.processing_stats = {
            "total_chunks_processed": 0,
            "successful_transcriptions": 0,
            "failed_transcriptions": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        logger.info("WhisperProcessor inicializado",
                   model=self.config.model_name,
                   device=self.config.device,
                   batch_size=self.config.batch_size)
    
    def _load_model(self):
        """Carrega modelo Whisper (thread-safe)"""
        with self.model_lock:
            if self.model is None:
                logger.info("Carregando modelo Whisper", 
                           model=self.config.model_name,
                           compute_type=self.config.compute_type)
                
                try:
                    # Usar faster-whisper se disponível e se compute_type for int8
                    if FASTER_WHISPER_AVAILABLE and self.config.compute_type == "int8":
                        logger.info("🚀 Usando faster-whisper com turbo mode")
                        
                        # Configurar device
                        if self.config.device == "cpu":
                            device = "cpu"
                        else:
                            device = "cuda" if torch.cuda.is_available() else "cpu"
                        
                        # Carregar modelo com faster-whisper
                        self.model = WhisperModel(
                            self.config.model_name,
                            device=device,
                            compute_type=self.config.compute_type
                        )
                        
                        logger.info("Modelo faster-whisper carregado com sucesso",
                                   model=self.config.model_name,
                                   device=device,
                                   compute_type=self.config.compute_type)
                    else:
                        # Usar whisper padrão
                        logger.info("📊 Usando whisper padrão")
                        
                        # Configurar device
                        if self.config.device == "cpu":
                            device = "cpu"
                        else:
                            device = "cuda" if torch.cuda.is_available() else "cpu"
                        
                        # Carregar modelo
                        self.model = whisper.load_model(
                            self.config.model_name,
                            device=device,
                            download_root=None
                        )
                        
                        # Configurar parâmetros
                        if hasattr(self.model, 'options'):
                            self.model.options.temperature = self.config.temperature
                            self.model.options.condition_on_previous_text = self.config.condition_on_previous_text
                        
                        logger.info("Modelo Whisper padrão carregado com sucesso",
                                   model=self.config.model_name,
                                   device=device)
                    
                except Exception as e:
                    logger.error("Erro ao carregar modelo Whisper", error=str(e))
                    raise
    
    def _get_cache_key(self, audio_data: np.ndarray, chunk_id: str) -> str:
        """Gera chave de cache para o chunk"""
        # Calcular hash do áudio + configurações
        audio_hash = hashlib.md5(audio_data.tobytes()).hexdigest()
        config_hash = hashlib.md5(
            f"{self.config.model_name}_{self.config.temperature}_{self.config.language}".encode()
        ).hexdigest()
        
        return f"{chunk_id}_{audio_hash}_{config_hash}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[WhisperResult]:
        """Obtém resultado do cache"""
        with self.cache_lock:
            if cache_key in self.cache:
                self.processing_stats["cache_hits"] += 1
                logger.debug("Cache hit", cache_key=cache_key)
                return self.cache[cache_key]
            
            self.processing_stats["cache_misses"] += 1
            return None
    
    def _save_to_cache(self, cache_key: str, result: WhisperResult):
        """Salva resultado no cache"""
        with self.cache_lock:
            # Limitar tamanho do cache (manter apenas últimos 100 resultados)
            if len(self.cache) > 100:
                # Remover entrada mais antiga
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            
            self.cache[cache_key] = result
            logger.debug("Resultado salvo no cache", cache_key=cache_key)
    
    def _preprocess_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Pré-processa áudio para Whisper"""
        try:
            # Whisper espera 16kHz
            if sample_rate != 16000:
                import librosa
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
    
    def transcribe_chunk(self, chunk_id: str, audio_data: np.ndarray, 
                        sample_rate: int, start_time: float, end_time: float,
                        progress_callback: Optional[Callable] = None) -> WhisperResult:
        """
        Transcreve um chunk individual
        """
        start_processing = time.time()
        
        try:
            # Verificar cache primeiro
            cache_key = self._get_cache_key(audio_data, chunk_id)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # Carregar modelo se necessário
            self._load_model()
            
            # Pré-processar áudio
            processed_audio = self._preprocess_audio(audio_data, sample_rate)
            
            # Configurar opções de transcrição
            options = {
                "temperature": self.config.temperature,
                "language": self.config.language,
                "task": self.config.task,
                "word_timestamps": self.config.word_timestamps,
                "condition_on_previous_text": self.config.condition_on_previous_text
            }
            
            if self.config.initial_prompt:
                options["initial_prompt"] = self.config.initial_prompt
            
            # Transcrever
            logger.debug("Iniciando transcrição", chunk_id=chunk_id)
            
            # Usar faster-whisper se disponível
            if FASTER_WHISPER_AVAILABLE and hasattr(self.model, 'transcribe') and hasattr(self.model.transcribe, '__call__'):
                # Verificar se é faster-whisper
                if hasattr(self.model, 'model'):
                    # faster-whisper
                    segments, info = self.model.transcribe(
                        processed_audio,
                        language=self.config.language,
                        task=self.config.task,
                        temperature=self.config.temperature,
                        word_timestamps=self.config.word_timestamps,
                        condition_on_previous_text=self.config.condition_on_previous_text
                    )
                    
                    # Converter resultado do faster-whisper para formato padrão
                    text = " ".join([segment.text for segment in segments])
                    result = {
                        "text": text,
                        "language": info.language,
                        "avg_logprob": info.avg_logprob if hasattr(info, 'avg_logprob') else 0.0,
                        "segments": [
                            {
                                "start": segment.start,
                                "end": segment.end,
                                "text": segment.text
                            } for segment in segments
                        ]
                    }
                else:
                    # whisper padrão
                    result = self.model.transcribe(
                        processed_audio,
                        **options
                    )
            else:
                # whisper padrão
                result = self.model.transcribe(
                    processed_audio,
                    **options
                )
            
            # Processar resultado
            processing_time = time.time() - start_processing
            
            whisper_result = WhisperResult(
                chunk_id=chunk_id,
                start_time=start_time,
                end_time=end_time,
                text=result.get("text", "").strip(),
                language=result.get("language", "unknown"),
                confidence=result.get("avg_logprob", 0.0),
                segments=result.get("segments", []),
                processing_time=processing_time,
                model_used=self.config.model_name
            )
            
            # Salvar no cache
            self._save_to_cache(cache_key, whisper_result)
            
            # Atualizar estatísticas
            self.processing_stats["total_chunks_processed"] += 1
            self.processing_stats["successful_transcriptions"] += 1
            self.processing_stats["total_processing_time"] += processing_time
            self.processing_stats["average_processing_time"] = (
                self.processing_stats["total_processing_time"] / 
                self.processing_stats["successful_transcriptions"]
            )
            
            logger.info("Transcrição concluída",
                       chunk_id=chunk_id,
                       text_length=len(whisper_result.text),
                       processing_time=f"{processing_time:.2f}s",
                       confidence=f"{whisper_result.confidence:.3f}")
            
            return whisper_result
            
        except Exception as e:
            processing_time = time.time() - start_processing
            error_msg = f"Erro na transcrição: {str(e)}"
            
            logger.error("Erro na transcrição",
                        chunk_id=chunk_id,
                        error=str(e),
                        processing_time=f"{processing_time:.2f}s")
            
            # Atualizar estatísticas
            self.processing_stats["total_chunks_processed"] += 1
            self.processing_stats["failed_transcriptions"] += 1
            
            return WhisperResult(
                chunk_id=chunk_id,
                start_time=start_time,
                end_time=end_time,
                text="",
                language="unknown",
                confidence=0.0,
                segments=[],
                processing_time=processing_time,
                model_used=self.config.model_name,
                error=error_msg
            )
    
    def transcribe_chunk_with_retry(self, chunk_id: str, audio_data: np.ndarray,
                                  sample_rate: int, start_time: float, end_time: float,
                                  progress_callback: Optional[Callable] = None) -> WhisperResult:
        """
        Transcreve chunk com retry automático
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = self.transcribe_chunk(
                    chunk_id, audio_data, sample_rate, start_time, end_time, progress_callback
                )
                
                # Se não houve erro, retornar resultado
                if not result.error:
                    return result
                
                last_error = result.error
                logger.warning(f"Tentativa {attempt + 1} falhou",
                             chunk_id=chunk_id,
                             error=last_error)
                
                # Aguardar antes da próxima tentativa
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff exponencial
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Tentativa {attempt + 1} falhou com exceção",
                           chunk_id=chunk_id,
                           error=last_error)
                
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        # Todas as tentativas falharam
        logger.error("Todas as tentativas falharam",
                    chunk_id=chunk_id,
                    max_retries=self.config.max_retries,
                    final_error=last_error)
        
        return WhisperResult(
            chunk_id=chunk_id,
            start_time=start_time,
            end_time=end_time,
            text="",
            language="unknown",
            confidence=0.0,
            segments=[],
            processing_time=0.0,
            model_used=self.config.model_name,
            error=f"Falha após {self.config.max_retries} tentativas: {last_error}"
        )
    
    def transcribe_batch(self, chunks: List[Tuple[str, np.ndarray, int, float, float]],
                        max_workers: Optional[int] = None,
                        progress_callback: Optional[Callable] = None) -> List[WhisperResult]:
        """
        Transcreve múltiplos chunks em paralelo
        """
        if not chunks:
            return []
        
        logger.info("Iniciando transcrição em lote",
                   total_chunks=len(chunks),
                   batch_size=self.config.batch_size)
        
        results = []
        
        # Usar ThreadPoolExecutor para processamento paralelo
        max_workers = max_workers or min(self.config.batch_size, len(chunks))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter jobs
            future_to_chunk = {}
            
            for chunk_id, audio_data, sample_rate, start_time, end_time in chunks:
                future = executor.submit(
                    self.transcribe_chunk_with_retry,
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
                    
                    logger.debug("Chunk processado",
                               chunk_id=chunk_id,
                               completed=f"{completed}/{len(chunks)}")
                    
                except Exception as e:
                    logger.error("Erro no processamento do chunk",
                               chunk_id=chunk_id,
                               error=str(e))
                    
                    # Criar resultado de erro
                    error_result = WhisperResult(
                        chunk_id=chunk_id,
                        start_time=0.0,
                        end_time=0.0,
                        text="",
                        language="unknown",
                        confidence=0.0,
                        segments=[],
                        processing_time=0.0,
                        model_used=self.config.model_name,
                        error=f"Erro no executor: {str(e)}"
                    )
                    results.append(error_result)
        
        # Ordenar resultados por chunk_id
        results.sort(key=lambda x: x.chunk_id)
        
        logger.info("Transcrição em lote concluída",
                   total_chunks=len(chunks),
                   successful=len([r for r in results if not r.error]),
                   failed=len([r for r in results if r.error]))
        
        return results
    
    def process_audio_chunks(self, chunks: List[Any],  # List[AudioChunk]
                           progress_callback: Optional[Callable] = None) -> List[WhisperResult]:
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
        
        return self.transcribe_batch(chunk_data, progress_callback=progress_callback)
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de processamento"""
        return self.processing_stats.copy()
    
    def clear_cache(self):
        """Limpa cache de resultados"""
        with self.cache_lock:
            self.cache.clear()
            logger.info("Cache limpo")
    
    def save_results(self, results: List[WhisperResult], output_path: str):
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
                    "text": result.text,
                    "language": result.language,
                    "confidence": result.confidence,
                    "segments": result.segments,
                    "processing_time": result.processing_time,
                    "model_used": result.model_used,
                    "error": result.error
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
        logger.info("Limpando recursos do WhisperProcessor")
        self.clear_cache()
        
        # Liberar modelo da memória
        with self.model_lock:
            if self.model is not None:
                del self.model
                self.model = None
        
        # Forçar garbage collection
        import gc
        gc.collect()
        
        logger.info("Recursos limpos")

# Função utilitária para transcrição simples
def transcribe_audio_file(file_path: str, output_path: Optional[str] = None,
                         model_name: str = "large-v3") -> WhisperResult:
    """
    Função utilitária para transcrição de arquivo único
    """
    import librosa
    
    # Carregar áudio
    audio_data, sample_rate = librosa.load(file_path, sr=16000)
    
    # Configurar processador
    config = WhisperConfig(model_name=model_name)
    processor = WhisperProcessor(config)
    
    # Transcrever
    result = processor.transcribe_chunk(
        "single_file",
        audio_data,
        sample_rate,
        0.0,
        len(audio_data) / sample_rate
    )
    
    # Salvar se output_path especificado
    if output_path:
        processor.save_results([result], output_path)
    
    # Limpeza
    processor.cleanup()
    
    return result 