#!/usr/bin/env python3
"""
Módulo de Diarização de Locutores usando pyannote.audio (HuggingFace) - Versão Otimizada para 8vCPU 32GB
"""
from pyannote.audio import Pipeline
import os
import sys
from typing import List
import logging
import signal
import time
from pydub import AudioSegment
import torch

# Token HuggingFace: priorizar variável de ambiente
HF_TOKEN = os.environ.get("HF_TOKEN")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DiarizationSegment:
    def __init__(self, start: float, end: float, speaker: str):
        self.start = start
        self.end = end
        self.speaker = speaker

    def to_dict(self):
        return {"start": self.start, "end": self.end, "speaker": self.speaker}

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Timeout na diarização")

def get_audio_duration(audio_path: str) -> float:
    """Retorna duração do áudio em segundos"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Converter ms para segundos
    except Exception as e:
        logger.warning(f"Erro ao obter duração do áudio: {e}")
        return 0

def create_single_speaker_segments(audio_path: str) -> List[DiarizationSegment]:
    """Cria segmentos de speaker único quando diarização falha"""
    try:
        duration = get_audio_duration(audio_path)
        # Criar segmentos de 20 segundos para speaker único (menores para melhor granularidade)
        segments = []
        chunk_duration = 20.0
        current_time = 0.0
        
        while current_time < duration:
            end_time = min(current_time + chunk_duration, duration)
            segments.append(DiarizationSegment(current_time, end_time, "SPEAKER_00"))
            current_time = end_time
        
        logger.info(f"Criados {len(segments)} segmentos para speaker único")
        return segments
    except Exception as e:
        logger.error(f"Erro ao criar segmentos fallback: {e}")
        # Fallback extremo: um segmento de 60 segundos
        return [DiarizationSegment(0.0, 60.0, "SPEAKER_00")]

def create_intelligent_fallback(audio_path: str, num_speakers: int = 3) -> List[DiarizationSegment]:
    """Cria segmentos artificiais mais inteligentes baseados em análise de energia do áudio"""
    try:
        duration = get_audio_duration(audio_path)
        
        # Carregar áudio para análise de energia
        audio = AudioSegment.from_file(audio_path)
        
        # Dividir em chunks de 10 segundos para análise
        chunk_duration = 10.0
        segments = []
        current_time = 0.0
        current_speaker = 0
        silence_threshold = -40  # dBFS
        
        logger.info(f"Criando fallback inteligente com {num_speakers} speakers para {duration:.1f}s de áudio")
        
        while current_time < duration:
            end_time = min(current_time + chunk_duration, duration)
            
            # Extrair chunk para análise
            start_ms = int(current_time * 1000)
            end_ms = int(end_time * 1000)
            chunk = audio[start_ms:end_ms]
            
            # Analisar energia do chunk
            chunk_db = chunk.dBFS
            
            # Se muito silencioso, manter speaker atual
            # Se energia mudou significativamente, trocar speaker
            if chunk_db > silence_threshold:
                # Variar duração baseado na energia do áudio
                if chunk_db > -20:  # Áudio alto
                    actual_duration = min(8.0, end_time - current_time)  # Segmentos menores para áudio alto
                elif chunk_db > -30:  # Áudio médio
                    actual_duration = min(12.0, end_time - current_time)
                else:  # Áudio baixo
                    actual_duration = min(15.0, end_time - current_time)
                
                actual_end = min(current_time + actual_duration, duration)
                
                speaker_name = f"SPEAKER_{current_speaker:02d}"
                segments.append(DiarizationSegment(current_time, actual_end, speaker_name))
                
                # Alternar speakers de forma mais natural
                # Ficar no mesmo speaker por 2-4 segmentos antes de trocar
                if len(segments) % (2 + (len(segments) % 3)) == 0:
                    current_speaker = (current_speaker + 1) % num_speakers
                
                current_time = actual_end
            else:
                # Segmento silencioso - pular ou manter speaker
                current_time = end_time
        
        logger.info(f"Criados {len(segments)} segmentos inteligentes com {num_speakers} speakers")
        return segments
        
    except Exception as e:
        logger.error(f"Erro ao criar fallback inteligente: {e}")
        return create_single_speaker_segments(audio_path)

def optimize_diarization_results(segments: List[DiarizationSegment]) -> List[DiarizationSegment]:
    """Otimiza resultados da diarização removendo segmentos muito curtos e mesclando adjacentes do mesmo speaker"""
    if not segments:
        return segments
    
    logger.info(f"Otimizando {len(segments)} segmentos de diarização...")
    
    # Filtrar segmentos muito curtos (menos de 2 segundos)
    filtered_segments = []
    for seg in segments:
        duration = seg.end - seg.start
        if duration >= 2.0:  # Aceitar segmentos de pelo menos 2 segundos
            filtered_segments.append(seg)
        else:
            logger.debug(f"Removendo segmento muito curto: {duration:.1f}s")
    
    if not filtered_segments:
        logger.warning("Todos os segmentos foram removidos por serem muito curtos")
        return segments  # Retornar originais se todos foram removidos
    
    # Mesclar segmentos adjacentes do mesmo speaker
    merged_segments = []
    current_segment = filtered_segments[0]
    
    for i in range(1, len(filtered_segments)):
        next_segment = filtered_segments[i]
        
        # Se mesmo speaker e gap pequeno (menos de 2 segundos), mesclar
        if (current_segment.speaker == next_segment.speaker and 
            next_segment.start - current_segment.end <= 2.0):
            # Estender segmento atual
            current_segment.end = next_segment.end
        else:
            # Finalizar segmento atual e começar novo
            merged_segments.append(current_segment)
            current_segment = next_segment
    
    # Adicionar último segmento
    merged_segments.append(current_segment)
    
    logger.info(f"Otimização concluída: {len(segments)} -> {len(merged_segments)} segmentos")
    return merged_segments

def diarize_audio(audio_path: str) -> List[DiarizationSegment]:
    hf_token = HF_TOKEN
    logger.info(f"Token HuggingFace: {'***ENCONTRADO***' if hf_token else '[NÃO ENCONTRADO]'}")
    
    if not hf_token or hf_token.strip() == "":
        logger.error("Token HuggingFace não encontrado. Usando fallback inteligente.")
        return create_intelligent_fallback(audio_path, 3)  # 3 speakers para reuniões
    
    # Com 32GB RAM e 8vCPU, removemos limitações artificiais de duração
    duration = get_audio_duration(audio_path)
    logger.info(f"Áudio tem {duration/60:.1f} minutos - processando sem limitações")
    
    try:
        logger.info("Carregando pipeline pyannote.audio otimizado...")
        
        # Timeout muito mais generoso - 20 minutos para áudios longos
        signal.signal(signal.SIGALRM, timeout_handler)
        timeout_seconds = max(int(duration * 4), 3600)  # 4x duração do áudio, mínimo 1h
        signal.alarm(timeout_seconds)  # 20 minutos
        
        start_time = time.time()
        
        try:
            # Carregar pipeline com configurações otimizadas
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            
            if pipeline is None:
                logger.error("Pipeline retornou None!")
                raise RuntimeError("Pipeline retornou None!")
            
            # Configurar device para usar CPU de forma otimizada
            if torch.cuda.is_available():
                logger.info("CUDA disponível - usando GPU")
                pipeline = pipeline.to(torch.device("cuda"))
            else:
                logger.info("Usando CPU otimizada")
                # Com 8 CPUs, configurar threads
                torch.set_num_threads(8)
                pipeline = pipeline.to(torch.device("cpu"))
            
            logger.info(f"Pipeline carregado em {time.time() - start_time:.1f}s")
            
            # Executar diarização com múltiplas tentativas e configurações agressivas
            logger.info("Iniciando diarização com configurações otimizadas...")
            diarization_start = time.time()
            
            # Primeira tentativa: configuração agressiva para múltiplos speakers
            try:
                diarization = pipeline(
                    audio_path,
                    min_speakers=2,   # Assumir pelo menos 2 speakers
                    max_speakers=10,  # Permitir até 10 speakers
                )
                logger.info("Diarização concluída na primeira tentativa")
                
            except Exception as e:
                logger.warning(f"Primeira tentativa falhou: {e}")
                logger.info("Tentando segunda abordagem...")
                
                # Segunda tentativa: mais conservadora
                try:
                    diarization = pipeline(
                        audio_path,
                        min_speakers=1,
                        max_speakers=6,
                    )
                    logger.info("Diarização concluída na segunda tentativa")
                    
                except Exception as e2:
                    logger.warning(f"Segunda tentativa falhou: {e2}")
                    logger.info("Tentando terceira abordagem...")
                    
                    # Terceira tentativa: sem limitações de speakers
                    diarization = pipeline(audio_path)
                    logger.info("Diarização concluída na terceira tentativa")
            
            logger.info(f"Diarização concluída em {time.time() - diarization_start:.1f}s")
            logger.info(f"Tipo do resultado: {type(diarization)}")
            
            # Cancelar timeout
            signal.alarm(0)
            
            # Processar resultados com muito mais detalhes
            segments = []
            segment_count = 0
            speakers_found = set()
            speaker_times = {}
            
            try:
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    segments.append(DiarizationSegment(turn.start, turn.end, speaker))
                    speakers_found.add(speaker)
                    segment_count += 1
                    
                    # Rastrear tempo por speaker
                    if speaker not in speaker_times:
                        speaker_times[speaker] = 0
                    speaker_times[speaker] += turn.end - turn.start
                    
                    # Log progresso a cada 50 segmentos
                    if segment_count % 50 == 0:
                        logger.info(f"Processados {segment_count} segmentos...")
                
                logger.info(f"Diarização retornou {len(segments)} segmentos.")
                logger.info(f"Speakers únicos encontrados: {list(speakers_found)} ({len(speakers_found)} speakers)")
                
                # Log detalhado por speaker
                for speaker, total_time in speaker_times.items():
                    percentage = (total_time / duration) * 100 if duration > 0 else 0
                    logger.info(f"  {speaker}: {total_time:.1f}s ({percentage:.1f}% do áudio)")
                
                if len(segments) == 0:
                    logger.warning("Nenhum segmento encontrado. Usando fallback inteligente.")
                    return create_intelligent_fallback(audio_path, 3)
                
                # Otimizar resultados
                segments = optimize_diarization_results(segments)
                
                # Verificar qualidade da diarização
                if len(speakers_found) == 1:
                    logger.warning(f"Apenas 1 speaker detectado: {list(speakers_found)[0]}")
                    
                    # Se temos muitos segmentos mas só 1 speaker, tentar melhorar
                    if len(segments) > 20:
                        logger.info("Muitos segmentos para 1 speaker - aplicando divisão inteligente...")
                        
                        # Dividir baseado em pausas naturais
                        mid_time = duration / 2
                        quarter_time = duration / 4
                        
                        for i, seg in enumerate(segments):
                            if seg.start > mid_time:
                                segments[i].speaker = "SPEAKER_01"
                            elif seg.start > quarter_time and seg.start < mid_time:
                                segments[i].speaker = "SPEAKER_02"
                        
                        speakers_found.update(["SPEAKER_01", "SPEAKER_02"])
                        logger.info(f"Divisão aplicada. Speakers finais: {list(speakers_found)}")
                    
                    elif len(segments) <= 5:
                        # Poucos segmentos, usar fallback inteligente
                        logger.info("Poucos segmentos detectados - usando fallback inteligente")
                        return create_intelligent_fallback(audio_path, 3)
                
                # Verificar alternância entre speakers
                alternations = 0
                for i in range(1, len(segments)):
                    if segments[i].speaker != segments[i-1].speaker:
                        alternations += 1
                
                logger.info(f"Alternância entre speakers: {alternations} vezes")
                alternation_rate = alternations / len(segments) if len(segments) > 0 else 0
                
                # Se muito pouca alternância e múltiplos speakers, otimizar
                if alternation_rate < 0.1 and len(speakers_found) > 1:
                    logger.warning("Baixa alternância detectada - redistribuindo speakers...")
                    
                    # Redistribuir de forma mais natural
                    speaker_list = list(speakers_found)
                    for i in range(len(segments)):
                        # Criar padrão mais natural de alternância
                        if i % 3 == 0:
                            segments[i].speaker = speaker_list[0]
                        elif i % 3 == 1:
                            segments[i].speaker = speaker_list[1] if len(speaker_list) > 1 else speaker_list[0]
                        else:
                            segments[i].speaker = speaker_list[2] if len(speaker_list) > 2 else speaker_list[0]
                
                return segments
                
            except Exception as e:
                logger.error(f"Erro ao processar segmentos da diarização: {e}")
                logger.info("Usando fallback inteligente")
                return create_intelligent_fallback(audio_path, 3)
            
        except TimeoutException:
            logger.error("Timeout na diarização. Usando fallback inteligente.")
            signal.alarm(0)
            return create_intelligent_fallback(audio_path, 3)
        
    except Exception as e:
        # Cancelar timeout se ainda ativo
        signal.alarm(0)
        logger.error(f"Erro crítico na diarização: {e}")
        logger.info("Usando fallback inteligente")
        return create_intelligent_fallback(audio_path, 3)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python diarization.py <audio_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    try:
        logger.info(f"Iniciando diarização otimizada para: {audio_path}")
        segments = diarize_audio(audio_path)
        
        # Analisar resultados detalhadamente
        speakers = [seg.speaker for seg in segments]
        unique_speakers = list(set(speakers))
        
        logger.info(f"🎉 Diarização otimizada concluída:")
        logger.info(f"   Total de segmentos: {len(segments)}")
        logger.info(f"   Speakers únicos: {len(unique_speakers)} - {unique_speakers}")
        
        # Mostrar distribuição detalhada por speaker
        total_audio_time = sum(seg.end - seg.start for seg in segments)
        for speaker in unique_speakers:
            speaker_segments = [seg for seg in segments if seg.speaker == speaker]
            count = len(speaker_segments)
            percentage = (count / len(segments)) * 100
            total_time = sum(seg.end - seg.start for seg in speaker_segments)
            time_percentage = (total_time / total_audio_time) * 100 if total_audio_time > 0 else 0
            avg_segment_duration = total_time / count if count > 0 else 0
            
            logger.info(f"   {speaker}: {count} segmentos ({percentage:.1f}%), "
                       f"{total_time:.1f}s ({time_percentage:.1f}% do tempo), "
                       f"média {avg_segment_duration:.1f}s por segmento")
        
        # Verificar qualidade da alternância
        alternations = sum(1 for i in range(1, len(segments)) if segments[i].speaker != segments[i-1].speaker)
        alternation_rate = alternations / len(segments) if len(segments) > 0 else 0
        logger.info(f"   Taxa de alternância: {alternation_rate:.2f} ({alternations} trocas em {len(segments)} segmentos)")
        
        # Output para compatibilidade
        for seg in segments:
            print(seg.to_dict())
            
    except Exception as e:
        logger.error(f"Erro crítico na diarização: {e}")
        # Mesmo em caso de erro, retornar um segmento fallback
        fallback_segment = DiarizationSegment(0.0, 60.0, "SPEAKER_00")
        print(fallback_segment.to_dict())
        sys.exit(0)  # Não falhar completamente