"""
Gestor de Recursos Robusto
Monitora uso de RAM e CPU em tempo real
Controla quantas instâncias de processamento podem rodar simultaneamente
Implementa queue com prioridades para jobs
"""

import psutil
import threading
import time
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from queue import PriorityQueue
import structlog

# Configuração de logging estruturado
logger = structlog.get_logger()

class JobPriority(Enum):
    """Prioridades de jobs"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0

class JobType(Enum):
    """Tipos de operação"""
    WHISPER = "whisper"
    DIARIZATION = "diarization"
    FULL_PIPELINE = "full_pipeline"
    AUDIO_PROCESSING = "audio_processing"

@dataclass
class ResourceLimits:
    """Limites de recursos por tipo de operação"""
    max_memory_gb: float = 56.0  # Aumentado para vídeos longos
    max_cpu_percent: float = 90.0
    max_concurrent_jobs: int = 1  # Reduzido para vídeos longos
    memory_alert_threshold: float = 45.0  # Aumentado
    cleanup_threshold: float = 30.0

@dataclass
class JobInfo:
    """Informações do job"""
    job_id: str
    job_type: JobType
    priority: JobPriority
    estimated_memory_gb: float
    estimated_duration_minutes: int
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: str = "pending"
    error: Optional[str] = None

class ResourceManager:
    """
    Gestor de recursos thread-safe para processamento paralelo
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.limits = ResourceLimits(**self.config.get("system", {}))
        
        # Queues e controle
        self.job_queue = PriorityQueue()
        self.active_jobs: Dict[str, JobInfo] = {}
        self.completed_jobs: List[JobInfo] = []
        
        # Controle de threads
        self.lock = threading.RLock()
        self.shutdown_event = threading.Event()
        
        # Monitoramento
        self.monitoring_thread = None
        self.metrics = {
            "total_jobs_processed": 0,
            "total_memory_used_gb": 0.0,
            "peak_memory_used_gb": 0.0,
            "average_processing_time_minutes": 0.0,
            "jobs_failed": 0,
            "memory_alerts": 0
        }
        
        # Callbacks
        self.memory_alert_callbacks: List[Callable] = []
        self.job_completion_callbacks: List[Callable] = []
        
        logger.info("ResourceManager inicializado", 
                   max_memory=self.limits.max_memory_gb,
                   max_jobs=self.limits.max_concurrent_jobs)
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Carrega configuração do arquivo"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Configuração padrão
        return {
            "system": {
                "max_memory_gb": 28.0,
                "max_cpu_percent": 90.0,
                "max_concurrent_jobs": 2,
                "memory_alert_threshold": 25.0,
                "cleanup_threshold": 30.0
            }
        }
    
    def start_monitoring(self):
        """Inicia thread de monitoramento"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self.monitoring_thread.start()
        logger.info("Monitoramento de recursos iniciado")
    
    def stop_monitoring(self):
        """Para thread de monitoramento"""
        self.shutdown_event.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitoramento de recursos parado")
    
    def _monitoring_loop(self):
        """Loop principal de monitoramento"""
        while not self.shutdown_event.is_set():
            try:
                self._check_system_resources()
                self._cleanup_old_jobs()
                time.sleep(30)  # Verificar a cada 30 segundos
            except Exception as e:
                logger.error("Erro no loop de monitoramento", error=str(e))
    
    def _check_system_resources(self):
        """Verifica recursos do sistema"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        memory_gb = memory.used / (1024**3)
        memory_percent = memory.percent
        
        # Atualizar métricas
        self.metrics["total_memory_used_gb"] = memory_gb
        if memory_gb > self.metrics["peak_memory_used_gb"]:
            self.metrics["peak_memory_used_gb"] = memory_gb
        
        # Verificar alertas
        if memory_gb > self.limits.memory_alert_threshold:
            self.metrics["memory_alerts"] += 1
            self._trigger_memory_alert(memory_gb, memory_percent)
        
        # Log de status
        logger.debug("Status dos recursos",
                    memory_gb=f"{memory_gb:.2f}",
                    memory_percent=f"{memory_percent:.1f}%",
                    cpu_percent=f"{cpu_percent:.1f}%",
                    active_jobs=len(self.active_jobs))
    
    def _trigger_memory_alert(self, memory_gb: float, memory_percent: float):
        """Dispara alertas de memória"""
        alert_msg = f"ALERTA: Memória alta - {memory_gb:.2f}GB ({memory_percent:.1f}%)"
        logger.warning(alert_msg)
        
        # Executar callbacks de alerta
        for callback in self.memory_alert_callbacks:
            try:
                callback(memory_gb, memory_percent)
            except Exception as e:
                logger.error("Erro no callback de alerta", error=str(e))
    
    def _cleanup_old_jobs(self):
        """Remove jobs antigos da memória"""
        current_time = time.time()
        cleanup_threshold = current_time - (self.config.get("performance", {}).get("cleanup_interval", 30) * 60)
        
        with self.lock:
            # Manter apenas jobs dos últimos 30 minutos
            self.completed_jobs = [
                job for job in self.completed_jobs 
                if job.completed_at and job.completed_at > cleanup_threshold
            ]
    
    def can_start_job(self, job_type: JobType, estimated_memory_gb: float) -> bool:
        """Verifica se pode iniciar novo job"""
        with self.lock:
            # Verificar limite de jobs simultâneos
            if len(self.active_jobs) >= self.limits.max_concurrent_jobs:
                return False
            
            # Verificar memória disponível
            current_memory = psutil.virtual_memory().used / (1024**3)
            if current_memory + estimated_memory_gb > self.limits.max_memory_gb:
                return False
            
            return True
    
    def submit_job(self, job_info: JobInfo) -> bool:
        """Submete job para processamento"""
        with self.lock:
            if not self.can_start_job(job_info.job_type, job_info.estimated_memory_gb):
                logger.warning("Job rejeitado - recursos insuficientes",
                             job_id=job_info.job_id,
                             job_type=job_info.job_type.value)
                return False
            
            # Adicionar à queue com prioridade
            priority = (job_info.priority.value, job_info.created_at)
            self.job_queue.put((priority, job_info))
            
            logger.info("Job submetido com sucesso",
                       job_id=job_info.job_id,
                       job_type=job_info.job_type.value,
                       priority=job_info.priority.value)
            return True
    
    def get_next_job(self) -> Optional[JobInfo]:
        """Obtém próximo job da queue"""
        try:
            if not self.job_queue.empty():
                priority, job_info = self.job_queue.get_nowait()
                return job_info
        except Exception as e:
            logger.error("Erro ao obter job da queue", error=str(e))
        
        return None
    
    def start_job(self, job_id: str):
        """Marca job como iniciado"""
        with self.lock:
            if job_id in self.active_jobs:
                self.active_jobs[job_id].started_at = time.time()
                self.active_jobs[job_id].status = "running"
                logger.info("Job iniciado", job_id=job_id)
    
    def complete_job(self, job_id: str, success: bool = True, error: Optional[str] = None):
        """Marca job como completado"""
        with self.lock:
            if job_id in self.active_jobs:
                job = self.active_jobs.pop(job_id)
                job.completed_at = time.time()
                job.status = "completed" if success else "failed"
                job.error = error
                
                # Calcular tempo de processamento
                if job.started_at:
                    processing_time = (job.completed_at - job.started_at) / 60  # minutos
                    self.metrics["average_processing_time_minutes"] = (
                        (self.metrics["average_processing_time_minutes"] * self.metrics["total_jobs_processed"] + processing_time) /
                        (self.metrics["total_jobs_processed"] + 1)
                    )
                
                self.metrics["total_jobs_processed"] += 1
                if not success:
                    self.metrics["jobs_failed"] += 1
                
                self.completed_jobs.append(job)
                
                # Executar callbacks de conclusão
                for callback in self.job_completion_callbacks:
                    try:
                        callback(job)
                    except Exception as e:
                        logger.error("Erro no callback de conclusão", error=str(e))
                
                logger.info("Job completado",
                           job_id=job_id,
                           success=success,
                           processing_time_minutes=processing_time if job.started_at else 0)
    
    def get_system_status(self) -> Dict:
        """Retorna status atual do sistema"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        return {
            "memory": {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent": memory.percent
            },
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "jobs": {
                "active": len(self.active_jobs),
                "queued": self.job_queue.qsize(),
                "completed": len(self.completed_jobs),
                "max_concurrent": self.limits.max_concurrent_jobs
            },
            "metrics": self.metrics.copy()
        }
    
    def get_metrics(self) -> Dict:
        """Retorna métricas do resource manager"""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                "memory_used_gb": memory.used / (1024**3),
                "memory_percent": memory.percent,
                "cpu_percent": cpu_percent,
                "active_jobs": len(self.active_jobs),
                "completed_jobs": len(self.completed_jobs),
                "total_jobs_processed": self.metrics["total_jobs_processed"],
                "jobs_failed": self.metrics["jobs_failed"],
                "peak_memory_used_gb": self.metrics["peak_memory_used_gb"]
            }
        except Exception as e:
            return {
                "error": str(e),
                "active_jobs": len(self.active_jobs),
                "completed_jobs": len(self.completed_jobs)
            }
    
    def add_memory_alert_callback(self, callback: Callable):
        """Adiciona callback para alertas de memória"""
        self.memory_alert_callbacks.append(callback)
    
    def add_job_completion_callback(self, callback: Callable):
        """Adiciona callback para conclusão de jobs"""
        self.job_completion_callbacks.append(callback)
    
    def emergency_cleanup(self):
        """Limpeza de emergência quando memória está crítica"""
        logger.warning("Executando limpeza de emergência")
        
        with self.lock:
            # Forçar garbage collection
            import gc
            gc.collect()
            
            # Limpar jobs antigos
            self.completed_jobs.clear()
            
            # Log de status após limpeza
            memory = psutil.virtual_memory()
            memory_gb = memory.used / (1024**3)
            logger.info("Limpeza de emergência concluída",
                       memory_after_cleanup=f"{memory_gb:.2f}GB")
    
    def shutdown(self):
        """Desliga o gestor de recursos"""
        logger.info("Desligando ResourceManager")
        self.stop_monitoring()
        self.shutdown_event.set()
        
        # Aguardar jobs ativos terminarem
        with self.lock:
            if self.active_jobs:
                logger.warning(f"Aguardando {len(self.active_jobs)} jobs ativos terminarem")
                # Em produção, você pode querer forçar o cancelamento
    
    def __enter__(self):
        """Context manager entry"""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()

# Função utilitária para criar JobInfo
def create_job_info(
    job_id: str,
    job_type: JobType,
    priority: JobPriority = JobPriority.NORMAL,
    estimated_memory_gb: float = 6.0,
    estimated_duration_minutes: int = 30
) -> JobInfo:
    """Cria JobInfo com valores padrão"""
    return JobInfo(
        job_id=job_id,
        job_type=job_type,
        priority=priority,
        estimated_memory_gb=estimated_memory_gb,
        estimated_duration_minutes=estimated_duration_minutes,
        created_at=time.time()
    ) 