#!/usr/bin/env python3
"""
ADAPTADOR PARA ARQUITETURA ROBUSTA DE DIARIZAÇÃO
===============================================
Este adaptador integra a nova arquitetura robusta com o sistema existente,
mantendo compatibilidade total com a API atual.
"""

import sys
import json
import logging
import os
import tempfile
import time
import asyncio
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sistema otimizado (sem diarização)
ROBUST_ARCHITECTURE_AVAILABLE = True
logger.info("✅ Sistema otimizado disponível")

# Fallback para sistema atual
try:
    from transcription import SmartTranscriptionPipeline
    CURRENT_SYSTEM_AVAILABLE = True
    logger.info("✅ Sistema atual disponível como fallback")
except ImportError as e:
    CURRENT_SYSTEM_AVAILABLE = False
    logger.warning(f"⚠️ Sistema atual não disponível: {e}")

class RobustTranscriptionAdapter:
    """
    Adaptador que integra a arquitetura robusta com o sistema existente
    """
    
    def __init__(self):
        self.robust_orchestrator = None
        self.resource_manager = None
        self.current_pipeline = None
        self.use_robust_architecture = False
        
        # Inicializar componentes
        self._initialize_components()
    
    def _initialize_components(self):
        """Inicializa os componentes disponíveis"""
        try:
            # Sistema otimizado (sem diarização)
            if ROBUST_ARCHITECTURE_AVAILABLE:
                logger.info("🚀 Sistema otimizado inicializado")
                self.use_robust_architecture = True
                
            else:
                # Fallback para sistema atual
                if CURRENT_SYSTEM_AVAILABLE:
                    logger.info("📊 Usando sistema atual como fallback")
                    self.current_pipeline = SmartTranscriptionPipeline()
                    self.use_robust_architecture = False
                else:
                    raise Exception("Nenhum sistema de transcrição disponível")
                    
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar componentes: {e}")
            # Tentar fallback
            if CURRENT_SYSTEM_AVAILABLE:
                logger.info("📊 Usando sistema atual como fallback")
                self.current_pipeline = SmartTranscriptionPipeline()
                self.use_robust_architecture = False
            else:
                raise Exception(f"Nenhum sistema disponível: {e}")
    
    async def transcribe_audio(self, audio_path: str, video_id: str = None) -> str:
        """
        Método principal de transcrição que usa a arquitetura robusta ou fallback
        """
        logger.info(f"🎯 Iniciando transcrição para {audio_path}")
        
        try:
            if self.use_robust_architecture:
                logger.info("🚀 Usando sistema otimizado")
                return await self._transcribe_with_robust_architecture(audio_path, video_id)
            else:
                logger.info("📊 Usando sistema atual")
                return await self._transcribe_with_current_system(audio_path, video_id)
                
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            raise
    
    async def _transcribe_with_robust_architecture(self, audio_path: str, video_id: str = None) -> str:
        """Transcrição usando Whisper direto SEM diarização"""
        try:
            # Detectar configuração baseada na duração
            audio_config = self._detect_audio_configuration(audio_path)
            logger.info(f"📊 Configuração detectada: {audio_config}")
            
            # Transcrever diretamente com Whisper (sem diarização)
            result = await self._transcribe_with_whisper_only(audio_path, audio_config)
            
            logger.info("✅ Transcrição concluída com sucesso (sem diarização)")
            return result
                
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            # Fallback para sistema atual
            if self.current_pipeline:
                logger.info("📊 Fallback para sistema atual")
                return await self._transcribe_with_current_system(audio_path, video_id)
            else:
                raise
    
    async def _transcribe_with_whisper_only(self, audio_path: str, config: Dict[str, Any]) -> str:
        """Transcrição direta com Whisper (sem diarização) com timestamps"""
        try:
            import whisper
            import librosa
            import numpy as np
            
            logger.info("🎯 Iniciando transcrição direta com Whisper")
            
            # Carregar modelo Whisper
            model_name = config.get("whisper_model", "large")
            logger.info(f"📦 Carregando modelo: {model_name}")
            
            # Usar faster-whisper se disponível e se compute_type for int8
            if config.get("compute_type") == "int8":
                try:
                    from faster_whisper import WhisperModel
                    logger.info("🚀 Usando faster-whisper com turbo mode")
                    model = WhisperModel(model_name, device="cpu", compute_type="int8")
                    
                    # Carregar áudio
                    audio_data, sample_rate = librosa.load(audio_path, sr=16000)
                    
                    # Transcrever
                    logger.info("📝 Transcrevendo áudio...")
                    segments, info = model.transcribe(
                        audio_data,
                        language="pt",
                        word_timestamps=True
                    )
                    
                    # Formatar com timestamps
                    transcription = self._format_transcription_with_timestamps(segments)
                    
                except ImportError:
                    logger.info("📊 Faster-whisper não disponível, usando whisper padrão")
                    # Fallback para whisper padrão
                    model = whisper.load_model(model_name)
                    
                    # Transcrever
                    logger.info("📝 Transcrevendo áudio...")
                    result = model.transcribe(
                        audio_path,
                        language="pt",
                        word_timestamps=True
                    )
                    
                    transcription = self._format_whisper_result_with_timestamps(result)
            else:
                # Usar whisper padrão
                logger.info("📊 Usando whisper padrão")
                model = whisper.load_model(model_name)
                
                # Transcrever
                logger.info("📝 Transcrevendo áudio...")
                result = model.transcribe(
                    audio_path,
                    language="pt",
                    word_timestamps=True
                )
                
                transcription = self._format_whisper_result_with_timestamps(result)
            
            logger.info(f"✅ Transcrição concluída: {len(transcription)} caracteres")
            return transcription
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição Whisper: {e}")
            raise
    
    def _format_transcription_with_timestamps(self, segments) -> str:
        """Formata transcrição do faster-whisper com timestamps"""
        try:
            formatted_lines = []
            
            for segment in segments:
                # Converter timestamps para formato legível
                start_time = self._format_timestamp(segment.start)
                end_time = self._format_timestamp(segment.end)
                
                # Formatar linha com timestamp
                line = f"[{start_time} → {end_time}] {segment.text.strip()}"
                formatted_lines.append(line)
            
            return "\n".join(formatted_lines)
            
        except Exception as e:
            logger.error(f"❌ Erro ao formatar timestamps: {e}")
            # Fallback: juntar apenas o texto
            return " ".join([segment.text for segment in segments])
    
    def _format_whisper_result_with_timestamps(self, result) -> str:
        """Formata resultado do whisper padrão com timestamps"""
        try:
            formatted_lines = []
            
            for segment in result.get("segments", []):
                # Converter timestamps para formato legível
                start_time = self._format_timestamp(segment.get("start", 0))
                end_time = self._format_timestamp(segment.get("end", 0))
                
                # Formatar linha com timestamp
                line = f"[{start_time} → {end_time}] {segment.get('text', '').strip()}"
                formatted_lines.append(line)
            
            return "\n".join(formatted_lines)
            
        except Exception as e:
            logger.error(f"❌ Erro ao formatar timestamps: {e}")
            # Fallback: retornar apenas o texto
            return result.get("text", "")
    
    def _format_timestamp(self, seconds: float) -> str:
        """Converte segundos para formato MM:SS ou HH:MM:SS"""
        try:
            if seconds < 3600:  # Menos de 1 hora
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes:02d}:{secs:02d}"
            else:  # 1 hora ou mais
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        except Exception as e:
            logger.error(f"❌ Erro ao formatar timestamp: {e}")
            return f"{seconds:.1f}s"
    
    async def _transcribe_with_current_system(self, audio_path: str, video_id: str = None) -> str:
        """Transcrição usando sistema atual"""
        try:
            if not self.current_pipeline:
                raise Exception("Sistema atual não disponível")
            
            result = await self.current_pipeline.process_audio(audio_path)
            logger.info("✅ Transcrição atual concluída com sucesso")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro no sistema atual: {e}")
            raise
    
    def _detect_audio_configuration(self, audio_path: str) -> Dict[str, Any]:
        """Detecta configuração otimizada baseada na duração do áudio"""
        try:
            import librosa
            
            # Carregar áudio para obter duração
            audio_data, sample_rate = librosa.load(audio_path, sr=16000)
            duration = len(audio_data) / sample_rate
            duration_hours = duration / 3600
            
            logger.info(f"🎵 Áudio detectado: {duration_hours:.2f} horas ({duration:.0f} segundos)")
            
            # Configuração baseada na duração
            if duration_hours > 1.0:  # Mais de 1 hora
                config = {
                    "whisper_model": "large",   # Large v1 com turbo
                    "compute_type": "int8",     # Turbo mode
                    "chunk_duration": 180.0,    # Chunks de 3 minutos (mais eficiente)
                    "chunk_overlap": 20.0,      # Overlap de 20 segundos
                    "max_concurrent_jobs": 1,   # Apenas 1 job por vez
                    "max_memory_gb": 25.0,      # Limite de memória para vídeos longos
                    "timeout_minutes": 0,       # Sem timeout para vídeos longos
                    "optimization": "long_video_turbo"
                }
                logger.info("🔧 Usando configuração para vídeo longo (>1h) - Large v1 TURBO - Sem timeout")
            elif duration_hours > 0.5:  # Entre 30 min e 1 hora
                config = {
                    "whisper_model": "large",   # Large v1 com turbo
                    "compute_type": "int8",     # Turbo mode
                    "chunk_duration": 90.0,     # Chunks de 1.5 minutos
                    "chunk_overlap": 15.0,      # Overlap de 15 segundos
                    "max_concurrent_jobs": 1,   # Apenas 1 job por vez
                    "max_memory_gb": 28.0,      # Limite padrão
                    "timeout_minutes": 0,       # Sem timeout para vídeos médios
                    "optimization": "medium_video_turbo"
                }
                logger.info("🔧 Usando configuração para vídeo médio (30min-1h) - Large v1 TURBO - Sem timeout")
            else:  # Menos de 30 minutos
                config = {
                    "whisper_model": "large",   # Large v1 com turbo
                    "compute_type": "int8",     # Turbo mode
                    "chunk_duration": 60.0,     # Chunks de 1 minuto
                    "chunk_overlap": 10.0,      # Overlap de 10 segundos
                    "max_concurrent_jobs": 2,   # 2 jobs simultâneos
                    "max_memory_gb": 28.0,      # Limite padrão
                    "timeout_minutes": 120,     # 2 horas de timeout (apenas para vídeos curtos)
                    "optimization": "short_video_turbo"
                }
                logger.info("🔧 Usando configuração para vídeo curto (<30min) - Large v1 TURBO")
            
            return config
            
        except Exception as e:
            logger.error(f"❌ Erro ao detectar configuração: {e}")
            # Configuração padrão conservadora
            return {
                "whisper_model": "large",  # Large v1 com turbo
                "compute_type": "int8",    # Turbo mode
                "chunk_duration": 90.0,
                "chunk_overlap": 15.0,
                "max_concurrent_jobs": 1,
                "max_memory_gb": 25.0,
                "timeout_minutes": 0,  # Sem timeout como padrão
                "optimization": "fallback_turbo"
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Retorna status dos sistemas disponíveis"""
        status = {
            "optimized_system_available": ROBUST_ARCHITECTURE_AVAILABLE,
            "current_system_available": CURRENT_SYSTEM_AVAILABLE,
            "using_optimized_system": self.use_robust_architecture,
            "current_pipeline_available": self.current_pipeline is not None,
            "features": {
                "whisper_turbo": True,
                "timestamps": True,
                "diarization": False,  # Desabilitado para velocidade
                "dynamic_config": True
            }
        }
        
        return status
    
    async def test_systems(self) -> Dict[str, Any]:
        """Testa todos os sistemas disponíveis"""
        results = {
            "robust_architecture": False,
            "current_system": False,
            "errors": []
        }
        
        # Testar arquitetura robusta
        if self.robust_orchestrator:
            try:
                # Criar arquivo de teste simples
                test_audio_path = self._create_test_audio()
                if test_audio_path:
                    result = await self.robust_orchestrator.process_file(test_audio_path)
                    results["robust_architecture"] = result.success
                    # Limpar arquivo de teste
                    os.remove(test_audio_path)
            except Exception as e:
                results["errors"].append(f"Robust architecture test failed: {e}")
        
        # Testar sistema atual
        if self.current_pipeline:
            try:
                test_audio_path = self._create_test_audio()
                if test_audio_path:
                    result = await self.current_pipeline.process_audio(test_audio_path)
                    results["current_system"] = bool(result and len(result) > 0)
                    # Limpar arquivo de teste
                    os.remove(test_audio_path)
            except Exception as e:
                results["errors"].append(f"Current system test failed: {e}")
        
        return results
    
    def _create_test_audio(self) -> Optional[str]:
        """Cria um arquivo de áudio de teste simples"""
        try:
            import numpy as np
            import soundfile as sf
            
            # Gerar 3 segundos de áudio de teste (440 Hz)
            sample_rate = 16000
            duration = 3.0
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio = 0.1 * np.sin(2 * np.pi * 440 * t)
            
            # Salvar arquivo temporário
            temp_path = tempfile.mktemp(suffix='.wav')
            sf.write(temp_path, audio, sample_rate)
            
            return temp_path
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível criar áudio de teste: {e}")
            return None

# Instância global do adaptador
_adapter_instance = None

def get_adapter() -> RobustTranscriptionAdapter:
    """Retorna instância global do adaptador"""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = RobustTranscriptionAdapter()
    return _adapter_instance

async def main():
    """Função principal para compatibilidade com o sistema existente"""
    if len(sys.argv) < 2:
        print("Uso: python robust_transcription_adapter.py <audio_path> [video_id]")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    video_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        adapter = get_adapter()
        
        # Verificar status dos sistemas
        status = adapter.get_system_status()
        logger.info(f"Status dos sistemas: {json.dumps(status, indent=2)}")
        
        # Executar transcrição
        start_time = time.time()
        transcription = await adapter.transcribe_audio(audio_path, video_id)
        duration = time.time() - start_time
        
        # Preparar resultado no formato esperado pelo sistema atual
        result = {
            "status": "success",
            "text": transcription,
            "language": "pt",  # Assumindo português
            "processing_type": "robust_architecture" if adapter.use_robust_architecture else "current_system",
            "timestamp": datetime.now().isoformat(),
            "diarization_available": adapter.use_robust_architecture,
            "processing_time_seconds": duration
        }
        
        # Imprimir resultado como JSON
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        error_result = {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 