#!/usr/bin/env python3
"""
Transcrição Otimizada e Robusta
- Chunks de 10 minutos para evitar travamentos
- Paralelismo real com múltiplos processos
- Logs detalhados de progresso
- Otimização máxima de CPU
- Monitoramento de recursos em tempo real
"""

import os
import sys
import json
import time
import logging
import subprocess
import psutil
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple
import whisper
import torch
import numpy as np
from pydub import AudioSegment
from pydub.effects import speedup
import tempfile
import shutil

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

class OptimizedTranscriber:
    def __init__(self):
        self.model = None
        self.max_workers = 2  # Máximo 2 workers
        self.cpus_per_worker = 4  # 4 CPUs por worker
        self.ram_per_worker_gb = 13  # 13GB RAM por worker
        self.audio_speed = 1.2  # 1.2x velocidade
        self.whisper_model = "large"  # Modelo large para qualidade
        self.chunk_duration = 600  # 10 minutos por chunk (600s)
        
    def log(self, message: str, level: str = "INFO"):
        """Log com timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def check_resources(self) -> Dict[str, Any]:
        """Verificar recursos disponíveis"""
        cpu_count = psutil.cpu_count()
        memory = psutil.virtual_memory()
        
        self.log(f"Recursos disponíveis: {cpu_count} CPUs, {memory.total / (1024**3):.1f}GB RAM")
        self.log(f"CPU atual: {psutil.cpu_percent()}%, RAM atual: {memory.percent}%")
        
        return {
            "cpu_count": cpu_count,
            "memory_total_gb": memory.total / (1024**3),
            "memory_available_gb": memory.available / (1024**3),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": memory.percent
        }
        
    def load_model(self):
        """Carregar modelo Whisper"""
        try:
            self.log(f"Carregando modelo Whisper {self.whisper_model}...")
            
            # Configurar PyTorch para os recursos especificados
            torch.set_num_threads(self.cpus_per_worker)
            torch.set_default_dtype(torch.float32)
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
            torch.set_grad_enabled(False)
            
            # Carregar modelo
            self.model = whisper.load_model(self.whisper_model, device="cpu")
            
            # Configurar modelo para velocidade
            if hasattr(self.model, 'encoder'):
                self.model.encoder.eval()
            if hasattr(self.model, 'decoder'):
                self.model.decoder.eval()
                
            self.log("Modelo carregado com sucesso!")
            
        except Exception as e:
            self.log(f"Erro ao carregar modelo: {e}", "ERROR")
            raise
            
    def speed_up_audio(self, audio_path: str) -> str:
        """Acelerar audio para 1.2x"""
        try:
            self.log(f"Acelerando audio para {self.audio_speed}x...")
            
            # Carregar audio
            audio = AudioSegment.from_file(audio_path)
            
            # Calcular nova duração
            original_duration = len(audio) / 1000  # em segundos
            new_duration = original_duration / self.audio_speed
            
            self.log(f"Duração original: {original_duration:.1f}s")
            self.log(f"Duração acelerada: {new_duration:.1f}s")
            
            # Acelerar audio
            fast_audio = speedup(audio, playback_speed=self.audio_speed)
            
            # Salvar arquivo temporário
            temp_path = audio_path.replace('.mp4', '_fast.wav').replace('.mp3', '_fast.wav')
            fast_audio.export(temp_path, format="wav")
            
            self.log(f"Audio acelerado salvo em: {temp_path}")
            return temp_path
            
        except Exception as e:
            self.log(f"Erro ao acelerar audio: {e}", "ERROR")
            return audio_path
            
    def split_audio_into_chunks(self, audio_path: str) -> List[Tuple[str, float, float]]:
        """Dividir audio em chunks de 10 minutos"""
        try:
            self.log(f"Dividindo audio em chunks de {self.chunk_duration}s...")
            
            # Carregar audio
            audio = AudioSegment.from_file(audio_path)
            duration_ms = len(audio)
            duration_s = duration_ms / 1000
            
            self.log(f"Duração total: {duration_s:.1f}s")
            
            chunks = []
            chunk_files = []
            
            # Calcular número de chunks
            num_chunks = int(np.ceil(duration_s / self.chunk_duration))
            self.log(f"Dividindo em {num_chunks} chunks...")
            
            for i in range(num_chunks):
                start_ms = i * self.chunk_duration * 1000
                end_ms = min((i + 1) * self.chunk_duration * 1000, duration_ms)
                
                # Extrair chunk
                chunk = audio[start_ms:end_ms]
                
                # Salvar chunk
                chunk_path = f"{audio_path}_chunk_{i:03d}.wav"
                chunk.export(chunk_path, format="wav")
                chunk_files.append(chunk_path)
                
                # Calcular timestamps reais
                start_time = start_ms / 1000
                end_time = end_ms / 1000
                
                chunks.append((chunk_path, start_time, end_time))
                
                self.log(f"Chunk {i+1}/{num_chunks}: {start_time:.1f}s - {end_time:.1f}s")
            
            self.log(f"Audio dividido em {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            self.log(f"Erro ao dividir audio: {e}", "ERROR")
            return [(audio_path, 0, duration_s)]
            
    def transcribe_chunk(self, chunk_info: Tuple[str, float, float]) -> Dict[str, Any]:
        """Transcrever um chunk específico"""
        chunk_path, start_time, end_time = chunk_info
        
        try:
            # Configurar processo para usar múltiplos cores
            torch.set_num_threads(self.cpus_per_worker)
            
            # Carregar modelo localmente para cada processo
            model = whisper.load_model(self.whisper_model, device="cpu")
            
            # Configurações otimizadas
            transcribe_options = {
                "beam_size": 3,
                "best_of": 2,
                "temperature": 0.0,
                "patience": 2,
                "length_penalty": 1.0,
                "word_timestamps": True,
                "condition_on_previous_text": False,
                "verbose": False,
                "fp16": False
            }
            
            # Transcrever chunk
            result = model.transcribe(chunk_path, **transcribe_options)
            
            # Ajustar timestamps para posição real no áudio
            for segment in result["segments"]:
                segment["start"] += start_time
                segment["end"] += start_time
                
                if "words" in segment:
                    for word in segment["words"]:
                        word["start"] += start_time
                        word["end"] += start_time
            
            # Limpar arquivo temporário
            try:
                os.remove(chunk_path)
            except:
                pass
            
            return {
                "success": True,
                "segments": result["segments"],
                "language": result.get("language", "pt"),
                "chunk_start": start_time,
                "chunk_end": end_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "segments": [],
                "chunk_start": start_time,
                "chunk_end": end_time
            }
            
    def transcribe_audio_parallel(self, audio_path: str) -> Dict[str, Any]:
        """Transcrever audio usando paralelismo"""
        try:
            self.log(f"Iniciando transcrição paralela do audio: {audio_path}")
            
            # Acelerar audio
            fast_audio_path = self.speed_up_audio(audio_path)
            
            # Dividir em chunks
            chunks = self.split_audio_into_chunks(fast_audio_path)
            
            if len(chunks) == 1:
                self.log("Audio pequeno, processando sem paralelismo...")
                return self.transcribe_chunk(chunks[0])
            
            # Processar chunks em paralelo
            self.log(f"Processando {len(chunks)} chunks em paralelo...")
            start_time = time.time()
            
            all_segments = []
            languages = set()
            
            # Usar ProcessPoolExecutor para paralelismo real
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Submeter todos os chunks
                future_to_chunk = {
                    executor.submit(self.transcribe_chunk, chunk): i 
                    for i, chunk in enumerate(chunks)
                }
                
                # Coletar resultados conforme completam
                completed_chunks = 0
                for future in as_completed(future_to_chunk):
                    chunk_index = future_to_chunk[future]
                    completed_chunks += 1
                    
                    try:
                        result = future.result()
                        
                        if result["success"]:
                            all_segments.extend(result["segments"])
                            if result["language"]:
                                languages.add(result["language"])
                            
                            self.log(f"Chunk {chunk_index + 1}/{len(chunks)} concluído - {len(result['segments'])} segmentos")
                        else:
                            self.log(f"Erro no chunk {chunk_index + 1}: {result['error']}", "ERROR")
                            
                    except Exception as e:
                        self.log(f"Erro ao processar chunk {chunk_index + 1}: {e}", "ERROR")
                    
                    # Log de progresso
                    progress = (completed_chunks / len(chunks)) * 100
                    self.log(f"Progresso: {progress:.1f}% ({completed_chunks}/{len(chunks)})")
            
            transcribe_time = time.time() - start_time
            
            # Ordenar segmentos por timestamp
            all_segments.sort(key=lambda x: x["start"])
            
            # Limpar arquivo temporário
            if fast_audio_path != audio_path:
                try:
                    os.remove(fast_audio_path)
                except:
                    pass
            
            self.log(f"Transcrição paralela concluída em {transcribe_time:.1f}s")
            self.log(f"Total de segmentos: {len(all_segments)}")
            
            return {
                "success": True,
                "segments": all_segments,
                "language": list(languages)[0] if languages else "pt",
                "transcribe_time": transcribe_time,
                "audio_duration": len(all_segments) * 30 if all_segments else 0,
                "chunks_processed": len(chunks)
            }
            
        except Exception as e:
            self.log(f"Erro na transcrição paralela: {e}", "ERROR")
            return {
                "success": False,
                "error": str(e),
                "segments": [],
                "language": "pt"
            }
            
    def post_process_text(self, text: str) -> str:
        """Pós-processamento do texto"""
        try:
            # Correções básicas
            corrections = {
                "vc": "você",
                "tb": "também",
                "pq": "porque",
                "q": "que",
                "n": "não",
                "ñ": "não",
                "tbm": "também",
                "vcs": "vocês",
                "hj": "hoje",
                "blz": "beleza",
                "vlw": "valeu",
                "obg": "obrigado",
                "obgd": "obrigado",
                "pfv": "por favor",
                "pf": "por favor",
                "mt": "muito",
                "mto": "muito",
                "tá": "está",
                "tô": "estou"
            }
            
            # Aplicar correções
            processed_text = text
            for wrong, correct in corrections.items():
                processed_text = processed_text.replace(f" {wrong} ", f" {correct} ")
                processed_text = processed_text.replace(f" {wrong}.", f" {correct}.")
                processed_text = processed_text.replace(f" {wrong},", f" {correct},")
                processed_text = processed_text.replace(f" {wrong}?", f" {correct}?")
                processed_text = processed_text.replace(f" {wrong}!", f" {correct}!")
            
            # Capitalização
            sentences = processed_text.split('. ')
            capitalized_sentences = []
            for sentence in sentences:
                if sentence.strip():
                    capitalized_sentences.append(sentence.strip().capitalize())
            
            processed_text = '. '.join(capitalized_sentences)
            
            return processed_text
            
        except Exception as e:
            return text
            
    def process_segments(self, segments: List[Dict]) -> List[Dict]:
        """Processar todos os segmentos"""
        try:
            self.log("Iniciando pós-processamento dos segmentos...")
            
            processed_segments = []
            improved_count = 0
            
            for i, segment in enumerate(segments):
                original_text = segment.get("text", "")
                
                # Pós-processar texto
                processed_text = self.post_process_text(original_text)
                
                # Log de progresso a cada 50 segmentos
                if (i + 1) % 50 == 0:
                    self.log(f"Processados {i + 1}/{len(segments)} segmentos...")
                
                # Verificar se houve melhoria
                if processed_text != original_text:
                    improved_count += 1
                
                # Atualizar segmento
                segment["text"] = processed_text
                segment["original_text"] = original_text
                processed_segments.append(segment)
            
            self.log(f"Pós-processamento concluído - {improved_count} segmentos melhorados")
            
            return processed_segments
            
        except Exception as e:
            self.log(f"Erro no processamento de segmentos: {e}", "ERROR")
            return segments
            
    def transcribe_video(self, video_path: str) -> Dict[str, Any]:
        """Transcrever vídeo completo com otimizações"""
        try:
            # Verificar recursos
            resources = self.check_resources()
            
            # Verificar se há recursos suficientes
            if resources["memory_available_gb"] < self.ram_per_worker_gb:
                raise Exception(f"RAM insuficiente. Necessário: {self.ram_per_worker_gb}GB, Disponível: {resources['memory_available_gb']:.1f}GB")
            
            # Carregar modelo se necessário
            if self.model is None:
                self.load_model()
            
            # Transcrever audio com paralelismo
            result = self.transcribe_audio_parallel(video_path)
            
            if not result["success"]:
                return result
            
            # Pós-processar segmentos
            processed_segments = self.process_segments(result["segments"])
            
            # Preparar resultado final
            final_result = {
                "success": True,
                "segments": processed_segments,
                "language": result["language"],
                "transcribe_time": result["transcribe_time"],
                "audio_duration": result["audio_duration"],
                "total_segments": len(processed_segments),
                "improved_segments": sum(1 for s in processed_segments if s.get("original_text") != s.get("text")),
                "chunks_processed": result.get("chunks_processed", 1),
                "resources_used": {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "cpus_per_worker": self.cpus_per_worker,
                    "max_workers": self.max_workers,
                    "ram_per_worker_gb": self.ram_per_worker_gb
                }
            }
            
            self.log(f"Transcrição completa concluída!")
            self.log(f"Segmentos: {final_result['total_segments']}")
            self.log(f"Melhorados: {final_result['improved_segments']}")
            self.log(f"Chunks: {final_result['chunks_processed']}")
            self.log(f"Tempo: {final_result['transcribe_time']:.1f}s")
            
            return final_result
            
        except Exception as e:
            self.log(f"Erro na transcrição do vídeo: {e}", "ERROR")
            return {
                "success": False,
                "error": str(e),
                "segments": [],
                "language": "pt"
            }

def main():
    """Função principal para uso direto"""
    if len(sys.argv) != 2:
        print("Uso: python transcribe_optimized.py <caminho_do_video>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    
    if not os.path.exists(video_path):
        print(f"Erro: Arquivo não encontrado: {video_path}")
        sys.exit(1)
    
    # Criar transcritor
    transcriber = OptimizedTranscriber()
    
    # Transcrever
    result = transcriber.transcribe_video(video_path)
    
    # Salvar resultado
    output_file = video_path.replace('.mp4', '_transcription.json').replace('.mp3', '_transcription.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Resultado salvo em: {output_file}")

if __name__ == "__main__":
    main() 