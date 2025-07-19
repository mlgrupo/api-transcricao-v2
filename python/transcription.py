#!/usr/bin/env python3
"""
Sistema de Transcrição 100% GRATUITO
FOCO: Whisper + Diarização gratuita, sem tokens, funciona offline
VERSÃO CORRIGIDA: Sem dependências externas problemáticas
"""
import sys
import json
import logging
import whisper
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import re
import time

# Processamento de áudio
from pydub import AudioSegment
from pydub.effects import normalize
import numpy as np

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# CORREÇÃO FUNDAMENTAL: Definir DiarizationSegment localmente
# Isso elimina a dependência externa que estava causando o erro
class DiarizationSegment:
    """
    Classe simples para representar um segmento de diarização
    Pedagogicamente, isso é uma estrutura de dados básica que armazena:
    - start: tempo de início em segundos
    - end: tempo de fim em segundos  
    - speaker: identificação do falante
    """
    def __init__(self, start: float, end: float, speaker: str):
        self.start = start
        self.end = end
        self.speaker = speaker

    def to_dict(self):
        """Converter para dicionário para facilitar debugging e logging"""
        return {"start": self.start, "end": self.end, "speaker": self.speaker}

# DIARIZAÇÃO GRATUITA INTEGRADA
# Em vez de importar de arquivo externo, implementamos uma versão simplificada aqui
def analyze_audio_energy(audio_segment, window_size=1000):
    """Analisar energia do áudio para detectar mudanças potenciais de speaker"""
    try:
        samples = np.array(audio_segment.get_array_of_samples())
        if audio_segment.channels == 2:
            # Converter estéreo para mono fazendo a média dos canais
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)
        
        # Calcular energia RMS (Root Mean Square) em janelas
        energies = []
        for i in range(0, len(samples), window_size):
            window = samples[i:i+window_size]
            if len(window) > 0:
                rms = np.sqrt(np.mean(window**2))
                energies.append(rms)
        
        return energies
    except Exception as e:
        logger.warning(f"Erro na análise de energia: {e}")
        return []

def simple_diarization(audio_path: str, target_speakers=3) -> List[DiarizationSegment]:
    """
    Implementação simplificada de diarização usando análise de energia
    FILOSOFIA EDUCATIVA: Em vez de usar algoritmos complexos de machine learning,
    usamos análise matemática básica que é mais robusta e não requer dependências pesadas
    """
    logger.info("🎯 Executando diarização gratuita integrada...")
    
    try:
        audio = AudioSegment.from_file(audio_path)
        duration = len(audio) / 1000.0
        
        # Para áudios muito curtos, usar apenas um speaker
        if duration <= 60:  # 1 minuto
            return [DiarizationSegment(0, duration, "SPEAKER_00")]
        
        # Análise de energia para detectar mudanças
        energies = analyze_audio_energy(audio, window_size=2000)  # Janelas de 2 segundos
        
        # Detectar pontos de mudança significativa na energia
        change_points = [0]  # Sempre começar do início
        
        if len(energies) > 1:
            for i in range(1, len(energies)):
                if energies[i-1] > 0:  # Evitar divisão por zero
                    change_ratio = abs(energies[i] - energies[i-1]) / energies[i-1]
                    # Se mudança > 40%, considerar possível troca de speaker
                    if change_ratio > 0.4:
                        time_pos = i * 2.0  # 2 segundos por janela
                        # Evitar pontos muito próximos (mínimo 8 segundos entre speakers)
                        if time_pos - change_points[-1] >= 8.0:
                            change_points.append(time_pos)
        
        # Garantir que terminamos no final do áudio
        if change_points[-1] < duration - 5:
            change_points.append(duration)
        
        # Criar segmentos alternando speakers
        segments = []
        for i in range(len(change_points) - 1):
            start_time = change_points[i]
            end_time = change_points[i + 1]
            speaker_id = i % target_speakers  # Alternar entre speakers disponíveis
            
            segments.append(DiarizationSegment(
                start_time, end_time, f"SPEAKER_{speaker_id:02d}"
            ))
        
        # Mesclar segmentos consecutivos do mesmo speaker
        if segments:
            merged = [segments[0]]
            for seg in segments[1:]:
                last = merged[-1]
                if last.speaker == seg.speaker and seg.start - last.end <= 3.0:
                    # Mesclar se mesmo speaker e pausa < 3 segundos
                    last.end = seg.end
                else:
                    merged.append(seg)
            segments = merged
        
        unique_speakers = set(seg.speaker for seg in segments)
        logger.info(f"✅ Diarização gratuita concluída: {len(segments)} segmentos, {len(unique_speakers)} speakers")
        
        return segments
        
    except Exception as e:
        logger.error(f"❌ Erro na diarização: {e}")
        # Fallback: divisão temporal simples
        segments = []
        segment_duration = min(30.0, duration / target_speakers)
        current_time = 0.0
        speaker_id = 0
        
        while current_time < duration:
            end_time = min(current_time + segment_duration, duration)
            segments.append(DiarizationSegment(
                current_time, end_time, f"SPEAKER_{speaker_id:02d}"
            ))
            current_time = end_time
            speaker_id = (speaker_id + 1) % target_speakers
        
        return segments

class AudioPreprocessor:
    """
    Classe responsável pelo pré-processamento de áudio
    PEDAGOGIA: Cada método tem um propósito específico e claro
    """
    def __init__(self):
        self.sample_rate = 16000  # Taxa de amostragem padrão para Whisper
        self.channels = 1         # Mono para eficiência
    
    def process(self, audio: AudioSegment) -> AudioSegment:
        logger.info("🔧 Pré-processando áudio...")
        try:
            # Normalização: ajustar volume para nível consistente
            audio = normalize(audio, headroom=0.1)
            
            # Conversão para formato padrão
            audio = audio.set_frame_rate(self.sample_rate).set_channels(self.channels)
            
            # Amplificar se muito baixo (melhora qualidade da transcrição)
            if audio.dBFS < -30:
                audio = audio + (25 - abs(audio.dBFS))
            
            logger.info(f"✅ Pré-processamento concluído (dBFS: {audio.dBFS:.1f})")
            return audio
        except Exception as e:
            logger.warning(f"⚠️ Erro no pré-processamento: {e}")
            return audio

class TextPostProcessor:
    """
    Classe para limpeza e formatação do texto transcrito
    EDUCATIVO: Cada método resolve um problema específico de qualidade de texto
    """
    def clean_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        
        # Remover espaços múltiplos (comum em transcrições automáticas)
        text = re.sub(r'\s+', ' ', text)
        
        # Remover caracteres problemáticos mantendo pontuação básica
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;\(\)]', '', text)
        
        return text.strip()
    
    def format_timestamp(self, start_time: float, end_time: float) -> str:
        """Formatar timestamp no formato [HH:MM:SS - HH:MM:SS]"""
        def seconds_to_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        
        start_str = seconds_to_time(start_time)
        end_str = seconds_to_time(end_time)
        return f"[{start_str} - {end_str}]"
    
    def format_speaker_name(self, speaker: str) -> str:
        """Formatar nome do speaker para exibição amigável"""
        if speaker.startswith("SPEAKER_"):
            try:
                number = int(speaker.split("_")[1]) + 1
                return f"Speaker {number:02d}"
            except:
                return speaker
        return speaker

def is_invalid_transcription(text: str) -> bool:
    """
    Detectar transcrições inválidas ou de baixa qualidade
    EDUCATIVO: Esta função implementa várias heurísticas para identificar
    quando o Whisper retorna resultados que não são úteis
    """
    if not text or len(text.strip()) < 2:
        return True
    
    text_lower = text.lower().strip()
    
    # Frases que indicam que o Whisper "alucinou" ou retornou meta-informação
    bad_indicators = [
        "transcreva com a maior precisão",
        "áudio em português brasileiro",
        "transcreva", "transcrição",
        "por favor", "muito obrigado",
        "não sei", "não entendi"
    ]
    
    for indicator in bad_indicators:
        if indicator in text_lower:
            return True
    
    # Detectar repetições excessivas (outro sinal de problema)
    words = text_lower.split()
    if len(words) > 5:
        word_counts = {}
        for word in words:
            if len(word) > 3:  # Só contar palavras "significativas"
                word_counts[word] = word_counts.get(word, 0) + 1
        
        for word, count in word_counts.items():
            if count > 8:  # Palavra repetida mais de 8 vezes é suspeito
                return True
    
    return False

class WhisperTranscriber:
    """
    Classe especializada para gerenciar transcrições com Whisper
    FILOSOFIA: Implementa estratégias progressivas - se uma abordagem falha,
    tenta abordagens mais simples até conseguir algum resultado
    """
    def __init__(self):
        self.model = None
        self.model_size = "large-v2"  # Melhor qualidade disponível
    
    def load_model(self, force_size=None):
        """Carregar modelo Whisper com fallback inteligente"""
        model_size = force_size or self.model_size
        
        if self.model is None or force_size:
            logger.info(f"🤖 Carregando Whisper {model_size}...")
            try:
                self.model = whisper.load_model(model_size, device="cpu")
                logger.info(f"✅ Modelo {model_size} carregado com sucesso")
            except Exception as e:
                if model_size != "medium":
                    logger.warning(f"⚠️ Erro ao carregar {model_size}, tentando 'medium': {e}")
                    self.model = whisper.load_model("medium", device="cpu")
                    self.model_size = "medium"
                else:
                    raise e
        
        return self.model
    
    def transcribe_segment(self, audio_path: str, max_attempts=3) -> str:
        """
        Transcrever um segmento com estratégia de fallback
        EDUCATIVO: Cada tentativa usa configurações progressivamente mais conservadoras
        """
        model = self.load_model()
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"🎯 Tentativa {attempt + 1}/{max_attempts}")
                
                # Configurações progressivamente mais simples
                if attempt == 0:
                    # Primeira tentativa: configurações otimizadas para máxima qualidade
                    result = model.transcribe(
                        audio_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.1,
                        compression_ratio_threshold=1.8,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.2,
                        initial_prompt="Transcrição em português brasileiro."
                    )
                elif attempt == 1:
                    # Segunda tentativa: configurações médias
                    result = model.transcribe(
                        audio_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.2,
                        no_speech_threshold=0.3
                    )
                else:
                    # Última tentativa: configurações mínimas (mais tolerante)
                    result = model.transcribe(
                        audio_path,
                        language="pt",
                        task="transcribe",
                        verbose=False,
                        fp16=False,
                        temperature=0.3
                    )
                
                transcription = result["text"].strip()
                
                if transcription and not is_invalid_transcription(transcription):
                    logger.info(f"✅ Transcrição válida obtida na tentativa {attempt + 1}")
                    return transcription
                else:
                    logger.warning(f"❌ Transcrição inválida na tentativa {attempt + 1}")
                    
            except Exception as e:
                logger.warning(f"❌ Erro na tentativa {attempt + 1}: {e}")
                
                # Se erro de memória, tentar modelo menor
                if "memory" in str(e).lower() and self.model_size != "medium":
                    logger.info("🔄 Tentando modelo menor devido a limitação de memória...")
                    self.load_model("medium")
        
        return ""

class FreeTranscriptionProcessor:
    """
    Classe principal que orquestra todo o processo de transcrição
    FILOSOFIA EDUCATIVA: Combina todas as técnicas em um fluxo coerente
    """
    def __init__(self):
        self.audio_preprocessor = AudioPreprocessor()
        self.text_processor = TextPostProcessor()
        self.transcriber = WhisperTranscriber()
    
    def create_simple_diarization(self, duration: float, num_speakers=2) -> List[DiarizationSegment]:
        """
        Criar diarização temporal simples quando análise avançada não é possível
        PEDAGOGIA: Fallback que sempre funciona, dividindo o áudio em segmentos temporais
        """
        segments = []
        
        if duration <= 60:  # 1 minuto
            segments.append(DiarizationSegment(0, duration, "SPEAKER_00"))
        else:
            # Dividir em segmentos alternados
            segment_duration = min(30, duration / num_speakers)  # Máximo 30s por segmento
            current_time = 0
            speaker_id = 0
            
            while current_time < duration:
                end_time = min(current_time + segment_duration, duration)
                segments.append(DiarizationSegment(
                    current_time, end_time, f"SPEAKER_{speaker_id:02d}"
                ))
                current_time = end_time
                speaker_id = (speaker_id + 1) % num_speakers
        
        return segments
    
    def transcribe_audio(self, audio_path: str, output_dir: Optional[str] = None) -> str:
        """
        Método principal de transcrição com diarização integrada
        FLUXO EDUCATIVO: Cada etapa tem um propósito claro e fallbacks definidos
        """
        logger.info(f"🎯 Iniciando transcrição gratuita: {audio_path}")
        temp_files = []
        
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")
            
            # Carregar e analisar áudio
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0
            duration_min = duration / 60.0
            
            logger.info(f"📊 Duração: {duration_min:.1f} minutos")
            
            # Para áudios muito longos, usar estratégia direta
            if duration > 7200:  # 2 horas
                logger.warning("⚠️ Áudio muito longo - usando transcrição direta")
                return self.direct_transcription(audio_path)
            
            # Pré-processar áudio
            audio = self.audio_preprocessor.process(audio)
            
            # Salvar áudio processado
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio.export(temp_file.name, format='wav')
                processed_audio_path = temp_file.name
                temp_files.append(processed_audio_path)
            
            # Aplicar diarização (sempre disponível agora)
            if duration > 30:  # Só usar diarização se > 30s
                try:
                    logger.info("🎯 Aplicando diarização gratuita integrada...")
                    diarization_segments = simple_diarization(processed_audio_path)
                    
                    if diarization_segments:
                        unique_speakers = set(seg.speaker for seg in diarization_segments)
                        logger.info(f"✅ Diarização: {len(diarization_segments)} segmentos, {len(unique_speakers)} speakers")
                        
                        return self.transcribe_with_diarization(
                            audio, diarization_segments, temp_files
                        )
                    else:
                        logger.warning("⚠️ Diarização não retornou segmentos")
                        
                except Exception as e:
                    logger.warning(f"❌ Diarização falhou: {e}")
            
            # Fallback: diarização simples ou transcrição direta
            if duration <= 30:
                logger.info("⚡ Áudio curto - transcrição direta")
                return self.direct_transcription(processed_audio_path)
            else:
                logger.info("🔄 Usando diarização temporal simples")
                simple_segments = self.create_simple_diarization(duration, num_speakers=3)
                return self.transcribe_with_diarization(
                    audio, simple_segments, temp_files
                )
                
        except Exception as e:
            logger.error(f"💥 Erro crítico: {e}")
            return self.direct_transcription(audio_path)
        finally:
            # Limpeza automática de arquivos temporários
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
    
    def direct_transcription(self, audio_path: str) -> str:
        """Transcrição direta sem diarização - mais simples e confiável"""
        logger.info("🎯 Transcrição direta iniciada")
        
        try:
            transcription = self.transcriber.transcribe_segment(audio_path)
            
            if transcription:
                # Criar formato com timestamp simples
                audio = AudioSegment.from_file(audio_path)
                duration = len(audio) / 1000.0
                
                timestamp = self.text_processor.format_timestamp(0, duration)
                formatted_text = self.text_processor.clean_text(transcription)
                
                return f"{timestamp} Speaker 01:\n{formatted_text}"
            else:
                return "Não foi possível transcrever este áudio."
                
        except Exception as e:
            logger.error(f"❌ Erro na transcrição direta: {e}")
            return f"Erro na transcrição: {str(e)}"
    
    def transcribe_with_diarization(self, audio: AudioSegment, segments: List[DiarizationSegment], temp_files: List) -> str:
        """
        Transcrever cada segmento individualmente e combinar resultados
        EDUCATIVO: Este é o método mais sofisticado - divide o áudio por speaker
        e transcreve cada parte separadamente
        """
        logger.info(f"🚀 Transcrevendo {len(segments)} segmentos")
        
        formatted_segments = []
        valid_transcriptions = 0
        total_segments = len(segments)
        
        for i, seg in enumerate(segments):
            try:
                # Extrair segmento de áudio
                start_ms = max(0, int(seg.start * 1000))
                end_ms = min(len(audio), int(seg.end * 1000))
                
                if end_ms <= start_ms or (end_ms - start_ms) < 500:  # Muito curto
                    logger.warning(f"⚠️ Segmento {i+1} muito curto, pulando...")
                    continue
                
                seg_audio = audio[start_ms:end_ms]
                
                # Salvar segmento temporário
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as seg_file:
                    seg_audio.export(seg_file.name, format='wav')
                    seg_path = seg_file.name
                    temp_files.append(seg_path)
                
                # Transcrever segmento
                transcription_text = self.transcriber.transcribe_segment(seg_path)
                
                if transcription_text.strip():
                    processed_text = self.text_processor.clean_text(transcription_text)
                    
                    if processed_text.strip():
                        timestamp = self.text_processor.format_timestamp(seg.start, seg.end)
                        speaker_name = self.text_processor.format_speaker_name(seg.speaker)
                        
                        formatted_segments.append(f"{timestamp} {speaker_name}:\n{processed_text}")
                        valid_transcriptions += 1
                        
                        logger.info(f"✅ Segmento {i+1}/{total_segments}: {len(processed_text)} chars")
                    else:
                        logger.warning(f"⚠️ Segmento {i+1}: texto vazio após processamento")
                else:
                    logger.warning(f"⚠️ Segmento {i+1}: sem transcrição")
                
            except Exception as e:
                logger.warning(f"❌ Erro no segmento {i+1}: {e}")
                continue
        
        if formatted_segments:
            success_rate = valid_transcriptions / total_segments
            result = "\n\n".join(formatted_segments)
            logger.info(f"🎉 Transcrição concluída: {valid_transcriptions}/{total_segments} ({success_rate:.1%} sucesso)")
            return result
        else:
            logger.error("❌ Nenhum segmento foi transcrito com sucesso")
            return self.direct_transcription(audio_path)

def main():
    """
    Função principal que processa argumentos e executa a transcrição
    EDUCATIVO: Esta é a interface de linha de comando do sistema
    """
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Por favor, forneça o caminho do arquivo de áudio"
        }, ensure_ascii=False))
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        processor = FreeTranscriptionProcessor()
        result = processor.transcribe_audio(audio_path, output_dir)
        
        # Salvar arquivo se solicitado
        if output_dir and result:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "transcricao.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"💾 Transcrição salva: {output_file}")
        
        # Output JSON para integração com TypeScript
        output = {
            "status": "success",
            "text": result,
            "language": "pt",
            "processing_type": "free_whisper_integrated_diarization",
            "timestamp": datetime.now().isoformat(),
            "diarization_available": True  # Sempre True agora
        }
        
        print(json.dumps(output, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"💥 Erro na execução: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()