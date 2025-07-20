"""
Orquestrador Principal
Integra todos os componentes anteriores
Gerencia processamento simultâneo de múltiplos arquivos
Implementa recovery automático em caso de falha parcial
Mantém logs detalhados de cada etapa
"""

import asyncio
import threading
import time
import uuid
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
import structlog
import json
from pathlib import Path
import psutil
import signal
import sys

# Importar componentes
from resource_manager import ResourceManager, JobType, JobPriority, create_job_info
from audio_chunker import AudioChunker, ChunkingConfig
from whisper_processor import WhisperProcessor, WhisperConfig
from speaker_diarizer import SpeakerDiarizer, DiarizationConfig
from transcription_merger import TranscriptionMerger, MergerConfig

logger = structlog.get_logger()

@dataclass
class ProcessingJob:
    """Job de processamento"""
    job_id: str
    file_path: str
    output_dir: str
    priority: JobPriority
    status: str = "pending"
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    progress: Dict[str, Any] = None

@dataclass
class OrchestratorConfig:
    """Configuração do orquestrador"""
    max_concurrent_jobs: int = 1  # Reduzido para vídeos longos
    max_memory_gb: float = 56.0  # Aumentado para vídeos longos
    chunk_duration: float = 90.0  # Chunks de 1.5 minutos (otimizado)
    chunk_overlap: float = 15.0  # Overlap otimizado
    whisper_model: str = "large"  # Large v1 com turbo
    compute_type: str = "int8"    # Turbo mode
    max_speakers: int = 8
    enable_recovery: bool = True
    enable_monitoring: bool = True
    log_interval: int = 60  # Logs menos frequentes
    cleanup_interval: int = 600  # 10 minutos

class DiarizationOrchestrator:
    """
    Orquestrador principal para processamento de diarização
    """
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self.resource_manager = ResourceManager()
        self.active_jobs: Dict[str, ProcessingJob] = {}
        self.completed_jobs: List[ProcessingJob] = []
        self.shutdown_event = threading.Event()
        
        # Componentes
        self.chunker = None
        self.whisper_processor = None
        self.diarizer = None
        self.merger = None
        
        # Controle de threads
        self.processing_thread = None
        self.monitoring_thread = None
        
        # Estatísticas
        self.stats = {
            "total_jobs_processed": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "peak_memory_usage": 0.0
        }
        
        logger.info("DiarizationOrchestrator inicializado",
                   max_concurrent_jobs=self.config.max_concurrent_jobs,
                   max_memory=self.config.max_memory_gb)
    
    def _initialize_components(self):
        """Inicializa componentes de processamento"""
        try:
            # Configurar chunker
            chunking_config = ChunkingConfig(
                chunk_duration=self.config.chunk_duration,
                overlap_duration=self.config.chunk_overlap
            )
            self.chunker = AudioChunker(chunking_config)
            
            # Configurar Whisper
            whisper_config = WhisperConfig(
                model_name=self.config.whisper_model,
                device="cpu",
                compute_type=self.config.compute_type
            )
            self.whisper_processor = WhisperProcessor(whisper_config)
            
            # Configurar diarizer
            diarization_config = DiarizationConfig(
                max_speakers=self.config.max_speakers,
                device="cpu"
            )
            self.diarizer = SpeakerDiarizer(diarization_config)
            
            # Configurar merger
            merger_config = MergerConfig()
            self.merger = TranscriptionMerger(merger_config)
            
            logger.info("Componentes inicializados com sucesso")
            
        except Exception as e:
            logger.error("Erro na inicialização dos componentes", error=str(e))
            raise
    
    def _cleanup_components(self):
        """Limpa recursos dos componentes"""
        try:
            if self.whisper_processor:
                self.whisper_processor.cleanup()
            if self.diarizer:
                self.diarizer.cleanup()
            if self.merger:
                pass  # Merger não tem cleanup específico
            
            logger.info("Componentes limpos")
            
        except Exception as e:
            logger.error("Erro na limpeza dos componentes", error=str(e))
    
    def _estimate_job_resources(self, file_path: str) -> Tuple[float, int]:
        """Estima recursos necessários para o job"""
        try:
            import librosa
            
            # Carregar áudio para obter duração
            audio_data, sample_rate = librosa.load(file_path, sr=16000)
            duration = len(audio_data) / sample_rate
            
            # Estimar memória baseada na duração
            # Para vídeos longos: ~300MB por hora + overhead dos modelos (otimizado)
            if duration > 3600:  # Mais de 1 hora
                estimated_memory_gb = (duration / 3600) * 0.3 + 10.0  # 10GB base para vídeos longos
            else:
                estimated_memory_gb = (duration / 3600) * 0.15 + 6.0  # 6GB base para modelos
            
            # Estimar tempo baseado na duração (otimizado com large v1)
            # Para vídeos longos: ~2x tempo real para processamento completo
            if duration > 3600:  # Mais de 1 hora
                estimated_minutes = int(duration / 60) * 2  # 2x mais lento para vídeos longos
            else:
                estimated_minutes = int(duration / 60) * 1.5  # 1.5x tempo real para vídeos normais
            
            logger.info(f"Estimativa de recursos para {duration/3600:.1f}h: {estimated_memory_gb:.1f}GB RAM, {estimated_minutes}min")
            
            return estimated_memory_gb, estimated_minutes
            
        except Exception as e:
            logger.error("Erro na estimativa de recursos", error=str(e))
            return 20.0, 180  # Valores padrão para vídeos longos
    
    def submit_job(self, file_path: str, output_dir: str, 
                  priority: JobPriority = JobPriority.NORMAL) -> str:
        """Submete job para processamento"""
        try:
            # Validar arquivo
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
            
            # Gerar ID único
            job_id = str(uuid.uuid4())
            
            # Estimar recursos
            estimated_memory_gb, estimated_minutes = self._estimate_job_resources(file_path)
            
            # Criar job
            job = ProcessingJob(
                job_id=job_id,
                file_path=file_path,
                output_dir=output_dir,
                priority=priority,
                created_at=time.time(),
                progress={
                    "stage": "pending",
                    "percent": 0,
                    "message": "Job submetido"
                }
            )
            
            # Submeter ao resource manager
            job_info = create_job_info(
                job_id=job_id,
                job_type=JobType.FULL_PIPELINE,
                priority=priority,
                estimated_memory_gb=estimated_memory_gb,
                estimated_duration_minutes=estimated_minutes
            )
            
            if self.resource_manager.submit_job(job_info):
                self.active_jobs[job_id] = job
                
                logger.info("Job submetido com sucesso",
                           job_id=job_id,
                           file_path=file_path,
                           estimated_memory_gb=f"{estimated_memory_gb:.2f}",
                           estimated_minutes=estimated_minutes)
                
                return job_id
            else:
                raise RuntimeError("Job rejeitado pelo ResourceManager")
                
        except Exception as e:
            logger.error("Erro ao submeter job", error=str(e))
            raise
    
    def _process_job(self, job: ProcessingJob):
        """Processa um job individual"""
        start_time = time.time()
        
        try:
            job.status = "processing"
            job.started_at = time.time()
            job.progress = {"stage": "initializing", "percent": 0, "message": "Inicializando"}
            
            logger.info("Iniciando processamento", job_id=job.job_id, file_path=job.file_path)
            
            # Criar diretório de saída
            output_path = Path(job.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Etapa 1: Chunking
            job.progress = {"stage": "chunking", "percent": 10, "message": "Dividindo áudio em chunks"}
            logger.info("Iniciando chunking", job_id=job.job_id)
            
            def chunking_progress(current, total, chunk):
                percent = 10 + (current / total) * 20  # 10-30%
                job.progress = {
                    "stage": "chunking",
                    "percent": int(percent),
                    "message": f"Chunk {current}/{total}"
                }
            
            chunks = self.chunker.process_file(
                job.file_path,
                output_dir=str(output_path / "chunks"),
                progress_callback=chunking_progress
            )
            
            if not chunks:
                raise RuntimeError("Nenhum chunk criado")
            
            logger.info("Chunking concluído", job_id=job.job_id, num_chunks=len(chunks))
            
            # Etapa 2: Transcrição Whisper
            job.progress = {"stage": "whisper", "percent": 30, "message": "Transcrevendo com Whisper"}
            logger.info("Iniciando transcrição Whisper", job_id=job.job_id)
            
            def whisper_progress(current, total, result):
                percent = 30 + (current / total) * 30  # 30-60%
                job.progress = {
                    "stage": "whisper",
                    "percent": int(percent),
                    "message": f"Transcrição {current}/{total}"
                }
            
            whisper_results = self.whisper_processor.process_audio_chunks(
                chunks, progress_callback=whisper_progress
            )
            
            # Salvar resultados Whisper
            whisper_output = output_path / "whisper_results.json"
            self.whisper_processor.save_results(whisper_results, str(whisper_output))
            
            logger.info("Transcrição Whisper concluída", job_id=job.job_id, results=len(whisper_results))
            
            # Etapa 3: Diarização
            job.progress = {"stage": "diarization", "percent": 60, "message": "Identificando speakers"}
            logger.info("Iniciando diarização", job_id=job.job_id)
            
            def diarization_progress(current, total, result):
                percent = 60 + (current / total) * 25  # 60-85%
                job.progress = {
                    "stage": "diarization",
                    "percent": int(percent),
                    "message": f"Diarização {current}/{total}"
                }
            
            diarization_results = self.diarizer.process_audio_chunks(
                chunks, progress_callback=diarization_progress
            )
            
            # Salvar resultados diarização
            diarization_output = output_path / "diarization_results.json"
            self.diarizer.save_results(diarization_results, str(diarization_output))
            
            logger.info("Diarização concluída", job_id=job.job_id, results=len(diarization_results))
            
            # Etapa 4: Merge
            job.progress = {"stage": "merging", "percent": 85, "message": "Combinando resultados"}
            logger.info("Iniciando merge", job_id=job.job_id)
            
            def merge_progress(current, total, segments):
                percent = 85 + (current / total) * 15  # 85-100%
                job.progress = {
                    "stage": "merging",
                    "percent": int(percent),
                    "message": f"Merge {current}/{total}"
                }
            
            merged_transcription = self.merger.merge_results(
                whisper_results, diarization_results, job.file_path, merge_progress
            )
            
            # Salvar resultado final
            final_output = output_path / "final_transcription.json"
            self.merger.save_merged_transcription(merged_transcription, str(final_output))
            
            # Exportar SRT
            srt_output = output_path / "transcription.srt"
            self.merger.export_srt(merged_transcription, str(srt_output))
            
            # Finalizar job
            processing_time = time.time() - start_time
            job.status = "completed"
            job.completed_at = time.time()
            job.progress = {"stage": "completed", "percent": 100, "message": "Processamento concluído"}
            
            # Atualizar estatísticas
            self.stats["total_jobs_processed"] += 1
            self.stats["successful_jobs"] += 1
            self.stats["total_processing_time"] += processing_time
            self.stats["average_processing_time"] = (
                self.stats["total_processing_time"] / self.stats["successful_jobs"]
            )
            
            logger.info("Job concluído com sucesso",
                       job_id=job.job_id,
                       processing_time=f"{processing_time:.2f}s",
                       total_segments=len(merged_transcription.segments),
                       total_speakers=len(merged_transcription.speakers))
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Erro no processamento: {str(e)}"
            
            job.status = "failed"
            job.completed_at = time.time()
            job.error = error_msg
            job.progress = {"stage": "failed", "percent": 0, "message": error_msg}
            
            # Atualizar estatísticas
            self.stats["total_jobs_processed"] += 1
            self.stats["failed_jobs"] += 1
            
            logger.error("Job falhou",
                        job_id=job.job_id,
                        error=str(e),
                        processing_time=f"{processing_time:.2f}s")
    
    def _processing_loop(self):
        """Loop principal de processamento"""
        while not self.shutdown_event.is_set():
            try:
                # Obter próximo job
                job_info = self.resource_manager.get_next_job()
                
                if job_info:
                    # Verificar se job ainda está ativo
                    if job_info.job_id in self.active_jobs:
                        job = self.active_jobs[job_info.job_id]
                        
                        # Marcar como iniciado
                        self.resource_manager.start_job(job_info.job_id)
                        
                        # Processar job
                        self._process_job(job)
                        
                        # Marcar como completado
                        success = job.status == "completed"
                        self.resource_manager.complete_job(job_info.job_id, success, job.error)
                        
                        # Mover para jobs completados
                        if job.job_id in self.active_jobs:
                            completed_job = self.active_jobs.pop(job.job_id)
                            self.completed_jobs.append(completed_job)
                
                else:
                    # Nenhum job disponível, aguardar
                    time.sleep(1)
                    
            except Exception as e:
                logger.error("Erro no loop de processamento", error=str(e))
                time.sleep(5)  # Aguardar antes de tentar novamente
    
    def _monitoring_loop(self):
        """Loop de monitoramento"""
        while not self.shutdown_event.is_set():
            try:
                # Verificar uso de memória
                memory = psutil.virtual_memory()
                memory_gb = memory.used / (1024**3)
                
                if memory_gb > self.stats["peak_memory_usage"]:
                    self.stats["peak_memory_usage"] = memory_gb
                
                # Log de status
                logger.info("Status do sistema",
                           active_jobs=len(self.active_jobs),
                           completed_jobs=len(self.completed_jobs),
                           memory_gb=f"{memory_gb:.2f}",
                           cpu_percent=psutil.cpu_percent())
                
                # Limpeza periódica
                if len(self.completed_jobs) > 100:
                    # Manter apenas os últimos 50 jobs
                    self.completed_jobs = self.completed_jobs[-50:]
                
                # Aguardar próximo ciclo
                time.sleep(self.config.log_interval)
                
            except Exception as e:
                logger.error("Erro no loop de monitoramento", error=str(e))
                time.sleep(30)
    
    def start(self):
        """Inicia o orquestrador"""
        try:
            logger.info("Iniciando DiarizationOrchestrator")
            
            # Inicializar componentes
            self._initialize_components()
            
            # Iniciar resource manager
            self.resource_manager.start_monitoring()
            
            # Iniciar thread de processamento
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True,
                name="ProcessingThread"
            )
            self.processing_thread.start()
            
            # Iniciar thread de monitoramento
            if self.config.enable_monitoring:
                self.monitoring_thread = threading.Thread(
                    target=self._monitoring_loop,
                    daemon=True,
                    name="MonitoringThread"
                )
                self.monitoring_thread.start()
            
            logger.info("Orquestrador iniciado com sucesso")
            
        except Exception as e:
            logger.error("Erro ao iniciar orquestrador", error=str(e))
            raise
    
    def stop(self):
        """Para o orquestrador"""
        logger.info("Parando DiarizationOrchestrator")
        
        # Sinalizar shutdown
        self.shutdown_event.set()
        
        # Parar resource manager
        self.resource_manager.stop_monitoring()
        
        # Aguardar threads terminarem
        if self.processing_thread:
            self.processing_thread.join(timeout=10)
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        
        # Limpar componentes
        self._cleanup_components()
        
        logger.info("Orquestrador parado")
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retorna status de um job"""
        # Verificar jobs ativos
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            return {
                "job_id": job.job_id,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "error": job.error
            }
        
        # Verificar jobs completados
        for job in self.completed_jobs:
            if job.job_id == job_id:
                return {
                    "job_id": job.job_id,
                    "status": job.status,
                    "progress": job.progress,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "error": job.error
                }
        
        return None
    
    def get_system_status(self) -> Dict[str, Any]:
        """Retorna status do sistema"""
        return {
            "active_jobs": len(self.active_jobs),
            "completed_jobs": len(self.completed_jobs),
            "resource_manager": self.resource_manager.get_system_status(),
            "orchestrator_stats": self.stats.copy()
        }
    
    def process_file(self, file_path: str, output_dir: str, 
                    priority: JobPriority = JobPriority.NORMAL) -> str:
        """
        API simples para processar arquivo
        """
        return self.submit_job(file_path, output_dir, priority)
    
    def process_file_with_config(self, file_path: str, output_dir: str, 
                                config: Dict[str, Any], 
                                priority: JobPriority = JobPriority.NORMAL) -> str:
        """
        API para processar arquivo com configuração personalizada
        """
        try:
            # Aplicar configuração personalizada
            self._apply_configuration(config)
            
            # Submeter job com configuração otimizada
            job_id = self.submit_job(file_path, output_dir, priority)
            
            logger.info(f"Job submetido com configuração otimizada: {config.get('optimization', 'unknown')}")
            return job_id
            
        except Exception as e:
            logger.error(f"Erro ao processar com configuração: {e}")
            # Fallback para configuração padrão
            return self.submit_job(file_path, output_dir, priority)
    
    def _apply_configuration(self, config: Dict[str, Any]):
        """Aplica configuração personalizada ao orquestrador"""
        try:
            # Atualizar configuração do orquestrador
            if "max_concurrent_jobs" in config:
                self.config.max_concurrent_jobs = config["max_concurrent_jobs"]
            
            if "max_memory_gb" in config:
                self.config.max_memory_gb = config["max_memory_gb"]
            
            if "chunk_duration" in config:
                self.config.chunk_duration = config["chunk_duration"]
            
            if "chunk_overlap" in config:
                self.config.chunk_overlap = config["chunk_overlap"]
            
            if "whisper_model" in config:
                self.config.whisper_model = config["whisper_model"]
            
            if "compute_type" in config:
                self.config.compute_type = config["compute_type"]
            
            # Atualizar resource manager
            if self.resource_manager and "max_memory_gb" in config:
                self.resource_manager.limits.max_memory_gb = config["max_memory_gb"]
            
            if self.resource_manager and "max_concurrent_jobs" in config:
                self.resource_manager.limits.max_concurrent_jobs = config["max_concurrent_jobs"]
            
            logger.info(f"Configuração aplicada: {config}")
            
        except Exception as e:
            logger.error(f"Erro ao aplicar configuração: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()

# Função utilitária para processamento simples
def process_audio_file(file_path: str, output_dir: str) -> str:
    """
    Função utilitária para processamento de arquivo único
    """
    config = OrchestratorConfig(max_concurrent_jobs=1)
    
    with DiarizationOrchestrator(config) as orchestrator:
        job_id = orchestrator.process_file(file_path, output_dir)
        
        # Aguardar conclusão
        while True:
            status = orchestrator.get_job_status(job_id)
            if status and status["status"] in ["completed", "failed"]:
                break
            time.sleep(5)
        
        return job_id

# Handler para graceful shutdown
def signal_handler(signum, frame):
    """Handler para sinais de shutdown"""
    logger.info(f"Recebido sinal {signum}, iniciando shutdown graceful")
    sys.exit(0)

# Registrar handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler) 