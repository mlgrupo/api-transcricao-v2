"""
Merger e Sincronização
Combina resultados de whisper + diarização com timestamps exatos
Resolve conflitos quando timestamps não batem perfeitamente
Implementa speaker tracking entre chunks
Detecta e corrige mudanças de speaker no meio de frases
"""

import numpy as np
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import structlog
import json
from pathlib import Path
from collections import defaultdict
import re

logger = structlog.get_logger()

@dataclass
class MergedSegment:
    """Segmento final com transcrição e speaker"""
    speaker_id: str
    start_time: float
    end_time: float
    text: str
    confidence: float
    chunk_id: str
    segment_index: int
    is_overlap: bool = False
    overlap_speakers: List[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class MergedTranscription:
    """Transcrição final completa"""
    file_path: str
    total_duration: float
    speakers: List[str]
    segments: List[MergedSegment]
    metadata: Dict[str, Any]
    processing_stats: Dict[str, Any]

@dataclass
class MergerConfig:
    """Configuração do merger"""
    overlap_threshold: float = 0.5  # segundos
    confidence_threshold: float = 0.5
    min_segment_duration: float = 0.5  # segundos
    max_gap_between_segments: float = 2.0  # segundos
    enable_speaker_correction: bool = True
    enable_text_cleaning: bool = True
    enable_overlap_detection: bool = True
    time_tolerance: float = 0.1  # segundos

class TranscriptionMerger:
    """
    Sistema de merge e sincronização de transcrições
    """
    
    def __init__(self, config: Optional[MergerConfig] = None):
        self.config = config or MergerConfig()
        self.processing_stats = {
            "total_segments_merged": 0,
            "overlap_segments": 0,
            "speaker_corrections": 0,
            "text_cleanups": 0,
            "processing_time": 0.0
        }
        
        logger.info("TranscriptionMerger inicializado",
                   overlap_threshold=self.config.overlap_threshold,
                   confidence_threshold=self.config.confidence_threshold)
    
    def _clean_text(self, text: str) -> str:
        """Limpa e normaliza texto"""
        if not self.config.enable_text_cleaning:
            return text
        
        # Remover espaços extras
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Normalizar pontuação
        text = re.sub(r'\.{2,}', '...', text)
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)
        
        # Remover caracteres especiais problemáticos
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)\[\]\{\}\"\']', '', text)
        
        return text
    
    def _find_overlapping_segments(self, whisper_segments: List[Dict], 
                                 diarization_segments: List[Any]) -> List[Tuple[Dict, Any]]:
        """Encontra segmentos que se sobrepõem temporalmente"""
        overlaps = []
        
        for whisper_seg in whisper_segments:
            whisper_start = whisper_seg.get('start', 0)
            whisper_end = whisper_seg.get('end', 0)
            
            for diarization_seg in diarization_segments:
                diarization_start = diarization_seg.start_time
                diarization_end = diarization_seg.end_time
                
                # Calcular sobreposição
                overlap_start = max(whisper_start, diarization_start)
                overlap_end = min(whisper_end, diarization_end)
                
                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    whisper_duration = whisper_end - whisper_start
                    diarization_duration = diarization_end - diarization_start
                    
                    # Calcular percentual de sobreposição
                    overlap_ratio = overlap_duration / min(whisper_duration, diarization_duration)
                    
                    if overlap_ratio > 0.3:  # 30% de sobreposição mínima
                        overlaps.append((whisper_seg, diarization_seg, overlap_ratio))
        
        # Ordenar por qualidade da sobreposição
        overlaps.sort(key=lambda x: x[2], reverse=True)
        
        return overlaps
    
    def _assign_speaker_to_text(self, whisper_segments: List[Dict], 
                              diarization_segments: List[Any]) -> List[Dict]:
        """Atribui speakers aos segmentos de texto"""
        assigned_segments = []
        
        for whisper_seg in whisper_segments:
            whisper_start = whisper_seg.get('start', 0)
            whisper_end = whisper_seg.get('end', 0)
            whisper_text = whisper_seg.get('text', '').strip()
            
            if not whisper_text:
                continue
            
            # Encontrar speaker que mais se sobrepõe
            best_speaker = None
            best_overlap = 0
            best_confidence = 0
            
            for diarization_seg in diarization_segments:
                diarization_start = diarization_seg.start_time
                diarization_end = diarization_seg.end_time
                
                # Calcular sobreposição
                overlap_start = max(whisper_start, diarization_start)
                overlap_end = min(whisper_end, diarization_end)
                
                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    whisper_duration = whisper_end - whisper_start
                    
                    overlap_ratio = overlap_duration / whisper_duration
                    
                    if overlap_ratio > best_overlap:
                        best_overlap = overlap_ratio
                        best_speaker = diarization_seg.speaker_id
                        best_confidence = diarization_seg.confidence
            
            # Criar segmento atribuído
            if best_speaker and best_overlap > 0.3:  # 30% de sobreposição mínima
                assigned_segment = {
                    'speaker_id': best_speaker,
                    'start_time': whisper_start,
                    'end_time': whisper_end,
                    'text': whisper_text,
                    'confidence': best_confidence,
                    'overlap_ratio': best_overlap,
                    'original_segment': whisper_seg
                }
                assigned_segments.append(assigned_segment)
            else:
                # Segmento sem speaker atribuído
                assigned_segment = {
                    'speaker_id': 'unknown',
                    'start_time': whisper_start,
                    'end_time': whisper_end,
                    'text': whisper_text,
                    'confidence': 0.0,
                    'overlap_ratio': 0.0,
                    'original_segment': whisper_seg
                }
                assigned_segments.append(assigned_segment)
        
        return assigned_segments
    
    def _detect_speaker_changes(self, segments: List[Dict]) -> List[Dict]:
        """Detecta e corrige mudanças de speaker no meio de frases"""
        if not self.config.enable_speaker_correction:
            return segments
        
        corrected_segments = []
        current_speaker = None
        current_text = ""
        current_start = 0
        current_confidence = 0
        
        for i, segment in enumerate(segments):
            speaker = segment['speaker_id']
            text = segment['text']
            
            # Se é o mesmo speaker, acumular texto
            if speaker == current_speaker or current_speaker is None:
                if current_speaker is None:
                    current_speaker = speaker
                    current_start = segment['start_time']
                    current_confidence = segment['confidence']
                
                current_text += " " + text if current_text else text
            else:
                # Mudança de speaker - salvar segmento anterior
                if current_text:
                    corrected_segments.append({
                        'speaker_id': current_speaker,
                        'start_time': current_start,
                        'end_time': segments[i-1]['end_time'],
                        'text': current_text.strip(),
                        'confidence': current_confidence,
                        'overlap_ratio': segments[i-1]['overlap_ratio'],
                        'original_segment': segments[i-1]['original_segment']
                    })
                
                # Iniciar novo segmento
                current_speaker = speaker
                current_text = text
                current_start = segment['start_time']
                current_confidence = segment['confidence']
        
        # Adicionar último segmento
        if current_text:
            corrected_segments.append({
                'speaker_id': current_speaker,
                'start_time': current_start,
                'end_time': segments[-1]['end_time'],
                'text': current_text.strip(),
                'confidence': current_confidence,
                'overlap_ratio': segments[-1]['overlap_ratio'],
                'original_segment': segments[-1]['original_segment']
            })
        
        return corrected_segments
    
    def _resolve_temporal_conflicts(self, segments: List[Dict]) -> List[Dict]:
        """Resolve conflitos temporais entre segmentos"""
        if not segments:
            return segments
        
        # Ordenar por tempo de início
        sorted_segments = sorted(segments, key=lambda x: x['start_time'])
        resolved_segments = []
        
        for i, segment in enumerate(sorted_segments):
            current_start = segment['start_time']
            current_end = segment['end_time']
            
            # Verificar sobreposição com segmento anterior
            if i > 0:
                prev_segment = resolved_segments[-1]
                prev_end = prev_segment['end_time']
                
                if current_start < prev_end:
                    # Há sobreposição - ajustar
                    overlap_duration = prev_end - current_start
                    
                    if overlap_duration > self.config.overlap_threshold:
                        # Sobreposição significativa - dividir no meio
                        mid_point = (prev_end + current_start) / 2
                        prev_segment['end_time'] = mid_point
                        segment['start_time'] = mid_point
                        
                        # Marcar como sobreposição
                        prev_segment['is_overlap'] = True
                        segment['is_overlap'] = True
                    else:
                        # Sobreposição pequena - ajustar para não sobrepor
                        segment['start_time'] = prev_end
            
            resolved_segments.append(segment)
        
        return resolved_segments
    
    def _merge_chunk_results(self, whisper_result: Any, diarization_result: Any) -> List[MergedSegment]:
        """Merge resultados de um chunk individual"""
        merged_segments = []
        
        try:
            # Extrair segmentos do Whisper
            whisper_segments = whisper_result.segments if hasattr(whisper_result, 'segments') else []
            
            # Extrair segmentos da diarização
            diarization_segments = diarization_result.segments if hasattr(diarization_result, 'segments') else []
            
            if not whisper_segments or not diarization_segments:
                logger.warning("Segmentos vazios", 
                             chunk_id=whisper_result.chunk_id,
                             whisper_segments=len(whisper_segments),
                             diarization_segments=len(diarization_segments))
                return merged_segments
            
            # Atribuir speakers ao texto
            assigned_segments = self._assign_speaker_to_text(whisper_segments, diarization_segments)
            
            # Detectar mudanças de speaker
            corrected_segments = self._detect_speaker_changes(assigned_segments)
            
            # Resolver conflitos temporais
            resolved_segments = self._resolve_temporal_conflicts(corrected_segments)
            
            # Converter para MergedSegment
            for i, segment in enumerate(resolved_segments):
                # Filtrar por duração mínima
                duration = segment['end_time'] - segment['start_time']
                if duration < self.config.min_segment_duration:
                    continue
                
                # Filtrar por confiança
                if segment['confidence'] < self.config.confidence_threshold:
                    continue
                
                # Limpar texto
                cleaned_text = self._clean_text(segment['text'])
                if not cleaned_text:
                    continue
                
                merged_segment = MergedSegment(
                    speaker_id=segment['speaker_id'],
                    start_time=segment['start_time'],
                    end_time=segment['end_time'],
                    text=cleaned_text,
                    confidence=segment['confidence'],
                    chunk_id=whisper_result.chunk_id,
                    segment_index=i,
                    is_overlap=segment.get('is_overlap', False),
                    metadata={
                        'overlap_ratio': segment.get('overlap_ratio', 0),
                        'original_segment': segment.get('original_segment', {})
                    }
                )
                
                merged_segments.append(merged_segment)
            
            logger.debug("Chunk processado",
                        chunk_id=whisper_result.chunk_id,
                        input_segments=len(whisper_segments),
                        output_segments=len(merged_segments))
            
        except Exception as e:
            logger.error("Erro no merge do chunk",
                        chunk_id=whisper_result.chunk_id,
                        error=str(e))
        
        return merged_segments
    
    def merge_results(self, whisper_results: List[Any], diarization_results: List[Any],
                     file_path: str, progress_callback: Optional[Callable] = None) -> MergedTranscription:
        """
        Merge resultados de Whisper e diarização
        """
        start_time = time.time()
        
        logger.info("Iniciando merge de resultados",
                   whisper_results=len(whisper_results),
                   diarization_results=len(diarization_results))
        
        # Criar dicionário de resultados por chunk_id
        whisper_dict = {result.chunk_id: result for result in whisper_results}
        diarization_dict = {result.chunk_id: result for result in diarization_results}
        
        all_merged_segments = []
        all_speakers = set()
        
        # Processar cada chunk
        for i, chunk_id in enumerate(whisper_dict.keys()):
            if chunk_id not in diarization_dict:
                logger.warning("Chunk não encontrado na diarização", chunk_id=chunk_id)
                continue
            
            whisper_result = whisper_dict[chunk_id]
            diarization_result = diarization_dict[chunk_id]
            
            # Merge do chunk
            merged_segments = self._merge_chunk_results(whisper_result, diarization_result)
            
            # Coletar speakers
            for segment in merged_segments:
                all_speakers.add(segment.speaker_id)
            
            all_merged_segments.extend(merged_segments)
            
            # Callback de progresso
            if progress_callback:
                progress_callback(i + 1, len(whisper_dict), merged_segments)
        
        # Ordenar segmentos por tempo
        all_merged_segments.sort(key=lambda x: x.start_time)
        
        # Calcular duração total
        total_duration = 0
        if all_merged_segments:
            total_duration = all_merged_segments[-1].end_time
        
        # Atualizar estatísticas
        processing_time = time.time() - start_time
        self.processing_stats.update({
            "total_segments_merged": len(all_merged_segments),
            "overlap_segments": len([s for s in all_merged_segments if s.is_overlap]),
            "processing_time": processing_time
        })
        
        # Criar resultado final
        merged_transcription = MergedTranscription(
            file_path=file_path,
            total_duration=total_duration,
            speakers=list(all_speakers),
            segments=all_merged_segments,
            metadata={
                "whisper_results": len(whisper_results),
                "diarization_results": len(diarization_results),
                "config": {
                    "overlap_threshold": self.config.overlap_threshold,
                    "confidence_threshold": self.config.confidence_threshold,
                    "min_segment_duration": self.config.min_segment_duration
                }
            },
            processing_stats=self.processing_stats.copy()
        )
        
        logger.info("Merge concluído",
                   total_segments=len(all_merged_segments),
                   total_speakers=len(all_speakers),
                   total_duration=f"{total_duration:.2f}s",
                   processing_time=f"{processing_time:.2f}s")
        
        return merged_transcription
    
    def save_merged_transcription(self, transcription: MergedTranscription, output_path: str):
        """Salva transcrição final em arquivo JSON"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Converter para formato serializável
            serializable_transcription = {
                "file_path": transcription.file_path,
                "total_duration": transcription.total_duration,
                "speakers": transcription.speakers,
                "metadata": transcription.metadata,
                "processing_stats": transcription.processing_stats,
                "segments": [
                    {
                        "speaker_id": segment.speaker_id,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "text": segment.text,
                        "confidence": segment.confidence,
                        "chunk_id": segment.chunk_id,
                        "segment_index": segment.segment_index,
                        "is_overlap": segment.is_overlap,
                        "metadata": segment.metadata
                    }
                    for segment in transcription.segments
                ]
            }
            
            # Salvar arquivo
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_transcription, f, indent=2, ensure_ascii=False)
            
            logger.info("Transcrição salva", output_path=str(output_path))
            
        except Exception as e:
            logger.error("Erro ao salvar transcrição", error=str(e))
            raise
    
    def export_srt(self, transcription: MergedTranscription, output_path: str):
        """Exporta transcrição em formato SRT"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(transcription.segments, 1):
                    # Formatar timestamps
                    start_time = self._format_timestamp(segment.start_time)
                    end_time = self._format_timestamp(segment.end_time)
                    
                    # Escrever entrada SRT
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"[{segment.speaker_id}] {segment.text}\n\n")
            
            logger.info("Arquivo SRT exportado", output_path=str(output_path))
            
        except Exception as e:
            logger.error("Erro ao exportar SRT", error=str(e))
            raise
    
    def _format_timestamp(self, seconds: float) -> str:
        """Formata timestamp para formato SRT (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def get_merge_statistics(self, transcription: MergedTranscription) -> Dict[str, Any]:
        """Retorna estatísticas do merge"""
        if not transcription.segments:
            return {}
        
        speaker_stats = defaultdict(lambda: {
            'total_segments': 0,
            'total_duration': 0.0,
            'total_words': 0,
            'avg_confidence': 0.0
        })
        
        for segment in transcription.segments:
            speaker = segment.speaker_id
            duration = segment.end_time - segment.start_time
            words = len(segment.text.split())
            
            speaker_stats[speaker]['total_segments'] += 1
            speaker_stats[speaker]['total_duration'] += duration
            speaker_stats[speaker]['total_words'] += words
            speaker_stats[speaker]['avg_confidence'] += segment.confidence
        
        # Calcular médias
        for speaker in speaker_stats:
            if speaker_stats[speaker]['total_segments'] > 0:
                speaker_stats[speaker]['avg_confidence'] /= speaker_stats[speaker]['total_segments']
        
        return {
            "total_segments": len(transcription.segments),
            "total_speakers": len(transcription.speakers),
            "total_duration": transcription.total_duration,
            "speaker_statistics": dict(speaker_stats),
            "overlap_segments": len([s for s in transcription.segments if s.is_overlap]),
            "avg_confidence": np.mean([s.confidence for s in transcription.segments])
        }

# Função utilitária para merge simples
def merge_transcription_results(whisper_results: List[Any], diarization_results: List[Any],
                              file_path: str, output_path: Optional[str] = None) -> MergedTranscription:
    """
    Função utilitária para merge de resultados
    """
    config = MergerConfig()
    merger = TranscriptionMerger(config)
    
    # Fazer merge
    transcription = merger.merge_results(whisper_results, diarization_results, file_path)
    
    # Salvar se output_path especificado
    if output_path:
        merger.save_merged_transcription(transcription, output_path)
    
    return transcription 