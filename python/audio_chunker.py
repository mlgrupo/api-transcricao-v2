"""
Processador de Chunks Inteligente
Divide áudio em chunks de 30s com overlap de 5s
Detecta pausas naturais para cortar em pontos ideais
Mantém metadados de timestamp original para cada chunk
Suporte formatos múltiplos (mp4, wav, m4a)
"""

import librosa
import numpy as np
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
# import webrtcvad  # Removido - não disponível no Windows
import wave
import tempfile
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass
import structlog
import time
import json

logger = structlog.get_logger()

@dataclass
class AudioChunk:
    """Representa um chunk de áudio"""
    chunk_id: str
    start_time: float  # Tempo de início em segundos
    end_time: float    # Tempo de fim em segundos
    duration: float    # Duração em segundos
    audio_data: np.ndarray
    sample_rate: int
    is_silent: bool = False
    silence_score: float = 0.0
    metadata: Dict[str, Any] = None

@dataclass
class ChunkingConfig:
    """Configuração para chunking"""
    chunk_duration: float = 30.0  # segundos
    overlap_duration: float = 5.0  # segundos
    min_silence_duration: float = 0.5  # segundos
    silence_threshold: float = -40.0  # dB
    vad_aggressiveness: int = 2  # 0-3
    sample_rate: int = 16000
    normalize_audio: bool = True
    remove_silence: bool = False

class AudioChunker:
    """
    Processador inteligente de chunks de áudio
    """
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        # self.vad = webrtcvad.Vad(self.config.vad_aggressiveness)  # Removido
        self.supported_formats = {'.mp4', '.wav', '.m4a', '.mp3', '.flac', '.aac'}
        
        logger.info("AudioChunker inicializado",
                   chunk_duration=self.config.chunk_duration,
                   overlap=self.config.overlap_duration,
                   sample_rate=self.config.sample_rate)
    
    def load_audio(self, file_path: str) -> Tuple[np.ndarray, int]:
        """
        Carrega áudio de diferentes formatos
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        if file_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Formato não suportado: {file_path.suffix}")
        
        logger.info("Carregando áudio", file_path=str(file_path))
        
        try:
            # Usar librosa para carregamento
            audio_data, sample_rate = librosa.load(
                str(file_path),
                sr=self.config.sample_rate,
                mono=True
            )
            
            # Normalizar se configurado
            if self.config.normalize_audio:
                audio_data = librosa.util.normalize(audio_data)
            
            logger.info("Áudio carregado com sucesso",
                       duration_seconds=len(audio_data) / sample_rate,
                       sample_rate=sample_rate,
                       shape=audio_data.shape)
            
            return audio_data, sample_rate
            
        except Exception as e:
            logger.error("Erro ao carregar áudio", error=str(e))
            raise
    
    def validate_audio_integrity(self, audio_data: np.ndarray, sample_rate: int) -> bool:
        """
        Valida integridade do áudio
        """
        try:
            # Verificar se não está vazio
            if len(audio_data) == 0:
                logger.error("Áudio vazio")
                return False
            
            # Verificar se não tem apenas zeros
            if np.all(audio_data == 0):
                logger.error("Áudio contém apenas silêncio")
                return False
            
            # Verificar se não tem valores NaN ou infinitos
            if np.any(np.isnan(audio_data)) or np.any(np.isinf(audio_data)):
                logger.error("Áudio contém valores NaN ou infinitos")
                return False
            
            # Verificar duração mínima (1 segundo)
            duration = len(audio_data) / sample_rate
            if duration < 1.0:
                logger.error(f"Duração muito curta: {duration:.2f}s")
                return False
            
            logger.info("Validação de integridade passou",
                       duration=duration,
                       max_amplitude=np.max(np.abs(audio_data)))
            return True
            
        except Exception as e:
            logger.error("Erro na validação de integridade", error=str(e))
            return False
    
    def detect_silence_segments(self, audio_data: np.ndarray, sample_rate: int) -> List[Tuple[float, float]]:
        """
        Detecta segmentos de silêncio usando energia do áudio
        """
        try:
            # Usar energia RMS para detectar silêncio
            frame_duration_ms = 30  # 30ms por frame
            frame_size = int(sample_rate * frame_duration_ms / 1000)
            
            silence_segments = []
            is_speaking = False
            silence_start = 0
            
            # Calcular energia RMS para cada frame
            for i in range(0, len(audio_data) - frame_size, frame_size):
                frame = audio_data[i:i + frame_size]
                
                # Calcular RMS (Root Mean Square) do frame
                rms = np.sqrt(np.mean(frame**2))
                
                # Converter RMS para dB
                if rms > 0:
                    rms_db = 20 * np.log10(rms)
                else:
                    rms_db = -100  # Silêncio total
                
                # Determinar se é silêncio baseado no threshold
                is_voice = rms_db > self.config.silence_threshold
                
                current_time = i / sample_rate
                
                if not is_voice and not is_speaking:
                    # Início de silêncio
                    silence_start = current_time
                    is_speaking = False
                elif is_voice and not is_speaking:
                    # Fim de silêncio
                    if current_time - silence_start >= self.config.min_silence_duration:
                        silence_segments.append((silence_start, current_time))
                    is_speaking = True
            
            # Verificar último segmento
            if not is_speaking and (len(audio_data) / sample_rate - silence_start) >= self.config.min_silence_duration:
                silence_segments.append((silence_start, len(audio_data) / sample_rate))
            
            logger.info(f"Detectados {len(silence_segments)} segmentos de silêncio")
            return silence_segments
            
        except Exception as e:
            logger.error("Erro na detecção de silêncio", error=str(e))
            return []
    
    def find_optimal_cut_points(self, audio_data: np.ndarray, sample_rate: int) -> List[float]:
        """
        Encontra pontos ideais para cortar baseado em silêncio
        """
        silence_segments = self.detect_silence_segments(audio_data, sample_rate)
        total_duration = len(audio_data) / sample_rate
        
        # Pontos de corte baseados na duração do chunk
        base_cut_points = []
        current_time = 0
        
        while current_time < total_duration:
            base_cut_points.append(current_time)
            current_time += self.config.chunk_duration - self.config.overlap_duration
        
        # Ajustar pontos de corte para pausas naturais
        optimal_cut_points = []
        
        for base_point in base_cut_points:
            best_point = base_point
            
            # Procurar por silêncio próximo ao ponto base
            for silence_start, silence_end in silence_segments:
                silence_center = (silence_start + silence_end) / 2
                
                # Se o centro do silêncio está próximo do ponto base, usar ele
                if abs(silence_center - base_point) < 2.0:  # 2 segundos de tolerância
                    best_point = silence_center
                    break
            
            optimal_cut_points.append(best_point)
        
        # Adicionar ponto final se necessário
        if optimal_cut_points and optimal_cut_points[-1] < total_duration:
            optimal_cut_points.append(total_duration)
        
        logger.info(f"Encontrados {len(optimal_cut_points)} pontos de corte otimizados")
        return optimal_cut_points
    
    def create_chunks(self, audio_data: np.ndarray, sample_rate: int, 
                     progress_callback: Optional[Callable] = None) -> List[AudioChunk]:
        """
        Cria chunks de áudio com overlap
        """
        if not self.validate_audio_integrity(audio_data, sample_rate):
            raise ValueError("Áudio não passou na validação de integridade")
        
        cut_points = self.find_optimal_cut_points(audio_data, sample_rate)
        chunks = []
        
        for i in range(len(cut_points) - 1):
            start_time = cut_points[i]
            end_time = cut_points[i + 1]
            
            # Converter para índices
            start_idx = int(start_time * sample_rate)
            end_idx = int(end_time * sample_rate)
            
            # Extrair chunk
            chunk_audio = audio_data[start_idx:end_idx]
            
            # Calcular score de silêncio
            silence_score = self._calculate_silence_score(chunk_audio)
            is_silent = silence_score > 0.8  # 80% silêncio
            
            # Criar chunk
            chunk = AudioChunk(
                chunk_id=f"chunk_{i:04d}",
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                audio_data=chunk_audio,
                sample_rate=sample_rate,
                is_silent=is_silent,
                silence_score=silence_score,
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(cut_points) - 1,
                    "cut_point_type": "optimal" if i > 0 else "start"
                }
            )
            
            chunks.append(chunk)
            
            # Callback de progresso
            if progress_callback:
                progress_callback(i + 1, len(cut_points) - 1, chunk)
        
        logger.info(f"Criados {len(chunks)} chunks de áudio",
                   total_duration=len(audio_data) / sample_rate,
                   avg_chunk_duration=np.mean([c.duration for c in chunks]))
        
        return chunks
    
    def _calculate_silence_score(self, audio_data: np.ndarray) -> float:
        """
        Calcula score de silêncio (0 = muito ruidoso, 1 = muito silencioso)
        """
        try:
            # Calcular RMS (Root Mean Square)
            rms = np.sqrt(np.mean(audio_data**2))
            
            # Converter para dB
            if rms > 0:
                db = 20 * np.log10(rms)
            else:
                db = -100
            
            # Normalizar para score entre 0 e 1
            # -60dB = muito silencioso, 0dB = muito ruidoso
            silence_score = max(0, min(1, (db + 60) / 60))
            
            return silence_score
            
        except Exception as e:
            logger.error("Erro no cálculo do score de silêncio", error=str(e))
            return 0.0
    
    def save_chunk(self, chunk: AudioChunk, output_path: str, format: str = "wav") -> bool:
        """
        Salva chunk em arquivo
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == "wav":
                sf.write(str(output_path), chunk.audio_data, chunk.sample_rate)
            else:
                # Usar pydub para outros formatos
                audio_segment = AudioSegment(
                    chunk.audio_data.tobytes(),
                    frame_rate=chunk.sample_rate,
                    sample_width=2,
                    channels=1
                )
                audio_segment.export(str(output_path), format=format)
            
            logger.debug(f"Chunk salvo: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar chunk: {e}")
            return False
    
    def process_file(self, file_path: str, output_dir: Optional[str] = None,
                    progress_callback: Optional[Callable] = None) -> List[AudioChunk]:
        """
        Processa arquivo completo e retorna chunks
        """
        logger.info("Iniciando processamento de arquivo", file_path=file_path)
        
        try:
            # Carregar áudio
            audio_data, sample_rate = self.load_audio(file_path)
            
            # Criar chunks
            chunks = self.create_chunks(audio_data, sample_rate, progress_callback)
            
            # Salvar chunks se output_dir especificado
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                
                for chunk in chunks:
                    chunk_filename = f"{chunk.chunk_id}.wav"
                    chunk_path = output_path / chunk_filename
                    self.save_chunk(chunk, str(chunk_path))
            
            # Salvar metadados
            if output_dir:
                metadata = {
                    "file_path": file_path,
                    "total_chunks": len(chunks),
                    "config": {
                        "chunk_duration": self.config.chunk_duration,
                        "overlap_duration": self.config.overlap_duration,
                        "sample_rate": self.config.sample_rate
                    },
                    "chunks": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "start_time": chunk.start_time,
                            "end_time": chunk.end_time,
                            "duration": chunk.duration,
                            "is_silent": chunk.is_silent,
                            "silence_score": chunk.silence_score
                        }
                        for chunk in chunks
                    ]
                }
                
                metadata_path = Path(output_dir) / "chunks_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
            
            logger.info("Processamento concluído",
                       total_chunks=len(chunks),
                       output_dir=output_dir)
            
            return chunks
            
        except Exception as e:
            logger.error("Erro no processamento do arquivo", error=str(e))
            raise
    
    def get_chunk_statistics(self, chunks: List[AudioChunk]) -> Dict[str, Any]:
        """
        Retorna estatísticas dos chunks
        """
        if not chunks:
            return {}
        
        durations = [chunk.duration for chunk in chunks]
        silence_scores = [chunk.silence_score for chunk in chunks]
        silent_chunks = [chunk for chunk in chunks if chunk.is_silent]
        
        return {
            "total_chunks": len(chunks),
            "total_duration": sum(durations),
            "avg_chunk_duration": np.mean(durations),
            "min_chunk_duration": np.min(durations),
            "max_chunk_duration": np.max(durations),
            "silent_chunks": len(silent_chunks),
            "silent_chunks_percent": len(silent_chunks) / len(chunks) * 100,
            "avg_silence_score": np.mean(silence_scores),
            "chunks_with_overlap": len([c for c in chunks if c.duration > self.config.chunk_duration])
        }

# Função utilitária para processamento simples
def chunk_audio_file(file_path: str, output_dir: Optional[str] = None,
                    chunk_duration: float = 30.0, overlap: float = 5.0) -> List[AudioChunk]:
    """
    Função utilitária para chunking simples
    """
    config = ChunkingConfig(
        chunk_duration=chunk_duration,
        overlap_duration=overlap
    )
    
    chunker = AudioChunker(config)
    return chunker.process_file(file_path, output_dir) 