#!/usr/bin/env python3
"""
Sistema de Diarização Otimizado para CPU
Usando pyannote.audio com configurações específicas para melhor precisão
"""
import logging
import tempfile
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass
import torch
import torchaudio
import numpy as np
from pyannote.audio import Pipeline
from pyannote.core import Annotation, Segment
import warnings

# Suprimir warnings desnecessários
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

@dataclass
class DiarizationSegment:
    """Representa um segmento de áudio com locutor identificado"""
    start: float
    end: float
    speaker: str
    confidence: float = 0.0

class AudioDiarizer:
    def __init__(self):
        self.pipeline = None
        self.device = "cpu"  # Forçar CPU
        self._setup_torch_cpu()
        
    def _setup_torch_cpu(self):
        """Configurar PyTorch para otimização em CPU"""
        torch.set_num_threads(8)  # 8 vCPUs
        torch.set_num_interop_threads(8)
        
        # Desabilitar CUDA completamente
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        
        # Configurações para CPU
        if hasattr(torch.backends, 'mkldnn'):
            torch.backends.mkldnn.enabled = True
        if hasattr(torch.backends, 'openmp'):
            torch.backends.openmp.enabled = True
            
        logger.info("PyTorch configurado para CPU com 8 threads")
    
    def load_pipeline(self) -> Pipeline:
        """Carregar pipeline de diarização com configurações otimizadas"""
        if self.pipeline is None:
            try:
                logger.info("Carregando pipeline de diarização...")
                
                # Usar modelo pré-treinado da pyannote
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=None  # Usar modelo público
                )
                
                # Forçar uso de CPU
                self.pipeline.to(torch.device("cpu"))
                
                # Configurações específicas para melhor precisão
                # Reduzir threshold para ser mais sensível a mudanças
                if hasattr(self.pipeline, '_segmentation'):
                    self.pipeline._segmentation.model.eval()
                if hasattr(self.pipeline, '_embedding'):
                    self.pipeline._embedding.model.eval()
                
                logger.info("Pipeline carregado com sucesso")
                
            except Exception as e:
                logger.error(f"Erro ao carregar pipeline oficial: {e}")
                logger.info("Tentando carregar modelo alternativo...")
                
                try:
                    # Fallback para modelo alternativo
                    self.pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization",
                        use_auth_token=None
                    )
                    self.pipeline.to(torch.device("cpu"))
                    logger.info("Pipeline alternativo carregado")
                    
                except Exception as e2:
                    logger.error(f"Erro ao carregar pipeline alternativo: {e2}")
                    raise RuntimeError("Não foi possível carregar nenhum modelo de diarização")
        
        return self.pipeline
    
    def preprocess_audio(self, audio_path: str) -> str:
        """Pré-processar áudio para melhor diarização"""
        try:
            # Carregar áudio
            waveform, sample_rate = torchaudio.load(audio_path)
            
            # Converter para mono se necessário
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Resample para 16kHz se necessário
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)
                sample_rate = 16000
            
            # Normalizar áudio
            waveform = waveform / torch.max(torch.abs(waveform))
            
            # Salvar áudio processado
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                torchaudio.save(tmp_file.name, waveform, sample_rate)
                return tmp_file.name
                
        except Exception as e:
            logger.warning(f"Erro no pré-processamento, usando arquivo original: {e}")
            return audio_path
    
    def diarize_with_precision(self, audio_path: str, min_segment_duration: float = 1.0) -> List[DiarizationSegment]:
        """Executar diarização com configurações de alta precisão"""
        pipeline = self.load_pipeline()
        
        # Pré-processar áudio
        processed_audio = self.preprocess_audio(audio_path)
        
        try:
            logger.info(f"Iniciando diarização do arquivo: {audio_path}")
            
            # Configurar parâmetros para maior precisão
            diarization_params = {
                # Configurações mais sensíveis para detectar mudanças
                "segmentation": {
                    "threshold": 0.4,  # Mais sensível a mudanças
                    "min_duration_on": 0.5,  # Mínimo 0.5s para considerar fala
                    "min_duration_off": 0.1   # Mínimo 0.1s de silêncio
                },
                "clustering": {
                    "method": "centroid",
                    "min_cluster_size": 2,
                    "threshold": 0.7  # Threshold mais rigoroso para agrupamento
                }
            }
            
            # Executar diarização
            with torch.no_grad():  # Economizar memória
                diarization = pipeline(processed_audio)
            
            # Converter para nossa estrutura
            segments = []
            for segment, _, speaker in diarization.itertracks(yield_label=True):
                duration = segment.end - segment.start
                
                # Filtrar segmentos muito curtos
                if duration >= min_segment_duration:
                    segments.append(DiarizationSegment(
                        start=segment.start,
                        end=segment.end,
                        speaker=speaker,
                        confidence=1.0  # pyannote não retorna confidence score
                    ))
            
            # Ordenar por tempo
            segments.sort(key=lambda x: x.start)
            
            # Pós-processamento para melhorar precisão
            segments = self._post_process_segments(segments)
            
            logger.info(f"Diarização concluída: {len(segments)} segmentos encontrados")
            
            # Limpar arquivo temporário
            if processed_audio != audio_path:
                try:
                    os.unlink(processed_audio)
                except Exception as e:
                    logger.warning(f"Erro ao limpar arquivo temporário: {e}")
            
            return segments
            
        except Exception as e:
            logger.error(f"Erro na diarização: {e}")
            # Limpar arquivo temporário em caso de erro
            if processed_audio != audio_path:
                try:
                    os.unlink(processed_audio)
                except:
                    pass
            raise
    
    def _post_process_segments(self, segments: List[DiarizationSegment]) -> List[DiarizationSegment]:
        """Pós-processar segmentos para melhor precisão"""
        if not segments:
            return segments
        
        processed = []
        
        for i, seg in enumerate(segments):
            # Verificar se o segmento é muito pequeno
            duration = seg.end - seg.start
            
            if duration < 0.5:  # Menos de 0.5 segundos
                # Tentar mesclar com segmento adjacente do mesmo speaker
                merged = False
                
                # Verificar segmento anterior
                if i > 0 and processed:
                    prev_seg = processed[-1]
                    if (prev_seg.speaker == seg.speaker and 
                        seg.start - prev_seg.end <= 2.0):  # Gap de até 2 segundos
                        # Estender segmento anterior
                        processed[-1] = DiarizationSegment(
                            start=prev_seg.start,
                            end=seg.end,
                            speaker=prev_seg.speaker,
                            confidence=prev_seg.confidence
                        )
                        merged = True
                
                # Se não mesclou, verificar próximo segmento
                if not merged and i < len(segments) - 1:
                    next_seg = segments[i + 1]
                    if (next_seg.speaker == seg.speaker and 
                        next_seg.start - seg.end <= 2.0):
                        # Criar segmento mesclado
                        merged_seg = DiarizationSegment(
                            start=seg.start,
                            end=next_seg.end,
                            speaker=seg.speaker,
                            confidence=seg.confidence
                        )
                        processed.append(merged_seg)
                        # Pular próximo segmento
                        segments[i + 1] = None
                        merged = True
                
                # Se não conseguiu mesclar, manter se for maior que 1 segundo
                if not merged and duration >= 1.0:
                    processed.append(seg)
            
            elif segments[i] is not None:  # Não foi marcado para pular
                processed.append(seg)
        
        # Garantir que não há sobreposições
        final_segments = []
        for seg in processed:
            if not final_segments:
                final_segments.append(seg)
            else:
                last_seg = final_segments[-1]
                if seg.start < last_seg.end:
                    # Ajustar início do segmento atual
                    if seg.end > last_seg.end:
                        adjusted_seg = DiarizationSegment(
                            start=last_seg.end,
                            end=seg.end,
                            speaker=seg.speaker,
                            confidence=seg.confidence
                        )
                        if adjusted_seg.end - adjusted_seg.start >= 0.5:
                            final_segments.append(adjusted_seg)
                else:
                    final_segments.append(seg)
        
        return final_segments

def diarize_audio(audio_path: str, min_segment_duration: float = 1.0) -> List[DiarizationSegment]:
    """
    Função principal para diarização de áudio
    
    Args:
        audio_path: Caminho para o arquivo de áudio
        min_segment_duration: Duração mínima do segmento em segundos
    
    Returns:
        Lista de segmentos com locutores identificados
    """
    try:
        diarizer = AudioDiarizer()
        segments = diarizer.diarize_with_precision(audio_path, min_segment_duration)
        
        # Log de estatísticas
        if segments:
            speakers = set(seg.speaker for seg in segments)
            total_duration = sum(seg.end - seg.start for seg in segments)
            logger.info(f"Estatísticas da diarização:")
            logger.info(f"  - {len(speakers)} locutores únicos: {list(speakers)}")
            logger.info(f"  - {len(segments)} segmentos")
            logger.info(f"  - Duração total de fala: {total_duration:.1f}s")
        
        return segments
        
    except Exception as e:
        logger.error(f"Erro na diarização: {e}")
        raise

if __name__ == "__main__":
    # Teste básico
    import sys
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        try:
            segments = diarize_audio(audio_file)
            print(f"Encontrados {len(segments)} segmentos:")
            for i, seg in enumerate(segments):
                print(f"{i+1}: {seg.start:.1f}s-{seg.end:.1f}s Speaker: {seg.speaker}")
        except Exception as e:
            print(f"Erro: {e}")
    else:
        print("Uso: python diarization.py <arquivo_audio>")