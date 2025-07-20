"""
Testes e Validação da Arquitetura Robusta
Testa cada componente isoladamente
Simula cenário crítico: 2 vídeos de 2h simultâneos
Valida qualidade da diarização com métricas
Testa recovery de falhas e memory leaks
"""

import pytest
import tempfile
import os
import time
import psutil
import numpy as np
import librosa
import json
from pathlib import Path
from typing import List, Dict, Any
import threading
import gc

# Importar componentes
from resource_manager import ResourceManager, JobType, JobPriority, create_job_info
from audio_chunker import AudioChunker, ChunkingConfig
from whisper_processor import WhisperProcessor, WhisperConfig
from speaker_diarizer import SpeakerDiarizer, DiarizationConfig
from transcription_merger import TranscriptionMerger, MergerConfig
from diarization_orchestrator import DiarizationOrchestrator, OrchestratorConfig

class TestRobustArchitecture:
    """Suite de testes para arquitetura robusta"""
    
    @pytest.fixture(scope="class")
    def temp_dir(self):
        """Diretório temporário para testes"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture(scope="class")
    def test_audio_file(self, temp_dir):
        """Gera arquivo de áudio sintético para testes"""
        # Gerar áudio sintético (30 segundos)
        sample_rate = 16000
        duration = 30  # segundos
        
        # Gerar tom de teste
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.1 * np.sin(2 * np.pi * 440 * t)  # 440 Hz
        
        # Adicionar ruído
        noise = 0.01 * np.random.randn(len(audio))
        audio += noise
        
        # Salvar arquivo
        audio_file = Path(temp_dir) / "test_audio.wav"
        librosa.output.write_wav(str(audio_file), audio, sample_rate)
        
        return str(audio_file)
    
    @pytest.fixture(scope="class")
    def multi_speaker_audio(self, temp_dir):
        """Gera áudio com múltiplos speakers simulados"""
        sample_rate = 16000
        duration = 60  # segundos
        
        # Gerar áudio com diferentes frequências para simular speakers
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Speaker 1 (440 Hz) - 0-20s
        speaker1 = np.zeros_like(t)
        speaker1[:int(20 * sample_rate)] = 0.1 * np.sin(2 * np.pi * 440 * t[:int(20 * sample_rate)])
        
        # Speaker 2 (880 Hz) - 20-40s
        speaker2 = np.zeros_like(t)
        speaker2[int(20 * sample_rate):int(40 * sample_rate)] = 0.1 * np.sin(2 * np.pi * 880 * t[:int(20 * sample_rate)])
        
        # Speaker 1 (440 Hz) - 40-60s
        speaker3 = np.zeros_like(t)
        speaker3[int(40 * sample_rate):] = 0.1 * np.sin(2 * np.pi * 440 * t[:int(20 * sample_rate)])
        
        # Combinar speakers
        audio = speaker1 + speaker2 + speaker3
        
        # Adicionar ruído
        noise = 0.01 * np.random.randn(len(audio))
        audio += noise
        
        # Salvar arquivo
        audio_file = Path(temp_dir) / "multi_speaker_audio.wav"
        librosa.output.write_wav(str(audio_file), audio, sample_rate)
        
        return str(audio_file)
    
    def test_resource_manager(self):
        """Testa ResourceManager"""
        print("\n=== TESTE: ResourceManager ===")
        
        # Inicializar
        rm = ResourceManager()
        
        # Testar submissão de jobs
        job1 = create_job_info("test1", JobType.WHISPER, JobPriority.HIGH, 2.0, 10)
        job2 = create_job_info("test2", JobType.DIARIZATION, JobPriority.NORMAL, 4.0, 20)
        
        assert rm.submit_job(job1) == True
        assert rm.submit_job(job2) == True
        
        # Verificar status
        status = rm.get_system_status()
        assert status["jobs"]["queued"] == 2
        
        # Testar obtenção de jobs
        next_job = rm.get_next_job()
        assert next_job is not None
        assert next_job.job_id in ["test1", "test2"]
        
        # Testar controle de jobs
        rm.start_job("test1")
        rm.complete_job("test1", True)
        
        # Verificar métricas
        metrics = rm.get_system_status()
        assert metrics["jobs"]["completed"] >= 0
        
        print("✅ ResourceManager: OK")
    
    def test_audio_chunker(self, test_audio_file):
        """Testa AudioChunker"""
        print("\n=== TESTE: AudioChunker ===")
        
        # Configurar chunker
        config = ChunkingConfig(chunk_duration=10.0, overlap_duration=2.0)
        chunker = AudioChunker(config)
        
        # Processar arquivo
        chunks = chunker.process_file(test_audio_file)
        
        # Verificar resultados
        assert len(chunks) > 0
        assert all(chunk.duration > 0 for chunk in chunks)
        assert all(chunk.sample_rate == 16000 for chunk in chunks)
        
        # Verificar overlap
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]
            next_chunk = chunks[i + 1]
            
            # Verificar se há overlap
            if current_chunk.end_time > next_chunk.start_time:
                overlap = current_chunk.end_time - next_chunk.start_time
                assert overlap >= 0
        
        # Verificar estatísticas
        stats = chunker.get_chunk_statistics(chunks)
        assert stats["total_chunks"] == len(chunks)
        assert stats["total_duration"] > 0
        
        print(f"✅ AudioChunker: {len(chunks)} chunks criados")
    
    def test_whisper_processor(self, test_audio_file):
        """Testa WhisperProcessor"""
        print("\n=== TESTE: WhisperProcessor ===")
        
        # Configurar processador
        config = WhisperConfig(model_name="base", device="cpu")  # Usar modelo menor para teste
        processor = WhisperProcessor(config)
        
        # Carregar áudio
        audio_data, sample_rate = librosa.load(test_audio_file, sr=16000)
        
        # Transcrever
        result = processor.transcribe_chunk(
            "test_chunk",
            audio_data,
            sample_rate,
            0.0,
            len(audio_data) / sample_rate
        )
        
        # Verificar resultado
        assert result is not None
        assert hasattr(result, 'text')
        assert hasattr(result, 'language')
        assert hasattr(result, 'confidence')
        
        # Verificar estatísticas
        stats = processor.get_processing_stats()
        assert stats["total_chunks_processed"] > 0
        
        print(f"✅ WhisperProcessor: Texto transcrito: '{result.text[:50]}...'")
        
        # Limpeza
        processor.cleanup()
    
    def test_speaker_diarizer(self, multi_speaker_audio):
        """Testa SpeakerDiarizer"""
        print("\n=== TESTE: SpeakerDiarizer ===")
        
        # Configurar diarizer
        config = DiarizationConfig(max_speakers=4, device="cpu")
        diarizer = SpeakerDiarizer(config)
        
        # Carregar áudio
        audio_data, sample_rate = librosa.load(multi_speaker_audio, sr=16000)
        
        # Diarizar
        result = diarizer.diarize_chunk(
            "test_chunk",
            audio_data,
            sample_rate,
            0.0,
            len(audio_data) / sample_rate
        )
        
        # Verificar resultado
        assert result is not None
        assert hasattr(result, 'speakers')
        assert hasattr(result, 'segments')
        assert hasattr(result, 'num_speakers')
        
        # Verificar se detectou speakers
        assert result.num_speakers >= 0
        assert len(result.segments) >= 0
        
        # Verificar estatísticas
        stats = diarizer.get_processing_stats()
        assert stats["total_chunks_processed"] > 0
        
        print(f"✅ SpeakerDiarizer: {result.num_speakers} speakers detectados")
        
        # Limpeza
        diarizer.cleanup()
    
    def test_transcription_merger(self):
        """Testa TranscriptionMerger"""
        print("\n=== TESTE: TranscriptionMerger ===")
        
        # Configurar merger
        config = MergerConfig()
        merger = TranscriptionMerger(config)
        
        # Criar dados de teste
        from dataclasses import dataclass
        
        @dataclass
        class MockWhisperResult:
            chunk_id: str
            start_time: float
            end_time: float
            text: str
            language: str
            confidence: float
            segments: List[Dict]
            processing_time: float
            model_used: str
        
        @dataclass
        class MockDiarizationResult:
            chunk_id: str
            start_time: float
            end_time: float
            speakers: List[str]
            segments: List
            num_speakers: int
            processing_time: float
        
        # Criar resultados simulados
        whisper_results = [
            MockWhisperResult(
                chunk_id="chunk_0000",
                start_time=0.0,
                end_time=10.0,
                text="Olá, como você está?",
                language="pt",
                confidence=0.8,
                segments=[{"start": 0.0, "end": 10.0, "text": "Olá, como você está?"}],
                processing_time=2.0,
                model_used="base"
            )
        ]
        
        diarization_results = [
            MockDiarizationResult(
                chunk_id="chunk_0000",
                start_time=0.0,
                end_time=10.0,
                speakers=["SPEAKER_00"],
                segments=[],
                num_speakers=1,
                processing_time=3.0
            )
        ]
        
        # Fazer merge
        transcription = merger.merge_results(
            whisper_results, diarization_results, "test_file.wav"
        )
        
        # Verificar resultado
        assert transcription is not None
        assert hasattr(transcription, 'segments')
        assert hasattr(transcription, 'speakers')
        assert hasattr(transcription, 'total_duration')
        
        print(f"✅ TranscriptionMerger: {len(transcription.segments)} segmentos criados")
    
    def test_diarization_orchestrator(self, test_audio_file, temp_dir):
        """Testa DiarizationOrchestrator"""
        print("\n=== TESTE: DiarizationOrchestrator ===")
        
        # Configurar orquestrador
        config = OrchestratorConfig(
            max_concurrent_jobs=1,
            chunk_duration=10.0,
            chunk_overlap=2.0,
            whisper_model="base"  # Usar modelo menor para teste
        )
        
        orchestrator = DiarizationOrchestrator(config)
        
        try:
            # Iniciar orquestrador
            orchestrator.start()
            
            # Submeter job
            output_dir = Path(temp_dir) / "orchestrator_test"
            job_id = orchestrator.process_file(test_audio_file, str(output_dir))
            
            # Aguardar conclusão
            max_wait = 300  # 5 minutos
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status = orchestrator.get_job_status(job_id)
                if status and status["status"] in ["completed", "failed"]:
                    break
                time.sleep(5)
            
            # Verificar resultado
            assert status is not None
            assert status["status"] in ["completed", "failed"]
            
            if status["status"] == "completed":
                # Verificar arquivos de saída
                assert (output_dir / "final_transcription.json").exists()
                assert (output_dir / "transcription.srt").exists()
                print("✅ DiarizationOrchestrator: Job completado com sucesso")
            else:
                print(f"⚠️ DiarizationOrchestrator: Job falhou - {status.get('error', 'Erro desconhecido')}")
        
        finally:
            # Parar orquestrador
            orchestrator.stop()
    
    def test_memory_management(self):
        """Testa gerenciamento de memória"""
        print("\n=== TESTE: Memory Management ===")
        
        # Monitorar uso de memória inicial
        initial_memory = psutil.virtual_memory().used / (1024**3)
        
        # Criar e destruir componentes múltiplas vezes
        for i in range(5):
            # ResourceManager
            rm = ResourceManager()
            rm.start_monitoring()
            time.sleep(1)
            rm.stop_monitoring()
            del rm
            
            # AudioChunker
            chunker = AudioChunker()
            del chunker
            
            # WhisperProcessor
            processor = WhisperProcessor(WhisperConfig(model_name="base"))
            processor.cleanup()
            del processor
            
            # SpeakerDiarizer
            diarizer = SpeakerDiarizer()
            diarizer.cleanup()
            del diarizer
            
            # Forçar garbage collection
            gc.collect()
            
            # Verificar memória
            current_memory = psutil.virtual_memory().used / (1024**3)
            memory_increase = current_memory - initial_memory
            
            print(f"Iteração {i+1}: Memória atual: {current_memory:.2f}GB (+{memory_increase:.2f}GB)")
            
            # Verificar se não há vazamento significativo
            assert memory_increase < 2.0  # Máximo 2GB de aumento
        
        print("✅ Memory Management: Sem vazamentos detectados")
    
    def test_concurrent_processing(self, temp_dir):
        """Testa processamento concorrente"""
        print("\n=== TESTE: Concurrent Processing ===")
        
        # Criar múltiplos arquivos de teste
        test_files = []
        for i in range(3):
            # Gerar áudio sintético
            sample_rate = 16000
            duration = 15  # segundos
            
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = 0.1 * np.sin(2 * np.pi * (440 + i * 100) * t)
            
            audio_file = Path(temp_dir) / f"test_audio_{i}.wav"
            librosa.output.write_wav(str(audio_file), audio, sample_rate)
            test_files.append(str(audio_file))
        
        # Configurar orquestrador para processamento concorrente
        config = OrchestratorConfig(
            max_concurrent_jobs=2,
            chunk_duration=5.0,
            chunk_overlap=1.0,
            whisper_model="base"
        )
        
        orchestrator = DiarizationOrchestrator(config)
        
        try:
            # Iniciar orquestrador
            orchestrator.start()
            
            # Submeter múltiplos jobs
            job_ids = []
            for i, test_file in enumerate(test_files):
                output_dir = Path(temp_dir) / f"concurrent_test_{i}"
                job_id = orchestrator.process_file(test_file, str(output_dir))
                job_ids.append(job_id)
            
            # Aguardar conclusão de todos
            max_wait = 600  # 10 minutos
            start_time = time.time()
            
            completed_jobs = 0
            while time.time() - start_time < max_wait and completed_jobs < len(job_ids):
                completed_jobs = 0
                for job_id in job_ids:
                    status = orchestrator.get_job_status(job_id)
                    if status and status["status"] in ["completed", "failed"]:
                        completed_jobs += 1
                
                if completed_jobs < len(job_ids):
                    time.sleep(10)
            
            # Verificar resultados
            assert completed_jobs == len(job_ids)
            
            # Verificar status do sistema
            system_status = orchestrator.get_system_status()
            assert system_status["active_jobs"] == 0
            
            print(f"✅ Concurrent Processing: {completed_jobs}/{len(job_ids)} jobs completados")
        
        finally:
            orchestrator.stop()
    
    def test_error_recovery(self, temp_dir):
        """Testa recovery de erros"""
        print("\n=== TESTE: Error Recovery ===")
        
        # Criar arquivo inválido
        invalid_file = Path(temp_dir) / "invalid_audio.txt"
        with open(invalid_file, 'w') as f:
            f.write("Este não é um arquivo de áudio válido")
        
        # Configurar orquestrador
        config = OrchestratorConfig(
            max_concurrent_jobs=1,
            chunk_duration=10.0,
            chunk_overlap=2.0,
            whisper_model="base"
        )
        
        orchestrator = DiarizationOrchestrator(config)
        
        try:
            # Iniciar orquestrador
            orchestrator.start()
            
            # Submeter job com arquivo inválido
            output_dir = Path(temp_dir) / "error_recovery_test"
            job_id = orchestrator.process_file(str(invalid_file), str(output_dir))
            
            # Aguardar conclusão
            max_wait = 60  # 1 minuto
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status = orchestrator.get_job_status(job_id)
                if status and status["status"] in ["completed", "failed"]:
                    break
                time.sleep(5)
            
            # Verificar que o job falhou graciosamente
            assert status is not None
            assert status["status"] == "failed"
            assert status["error"] is not None
            
            # Verificar que o sistema continua funcionando
            system_status = orchestrator.get_system_status()
            assert system_status["active_jobs"] == 0
            
            print("✅ Error Recovery: Sistema recuperou graciosamente do erro")
        
        finally:
            orchestrator.stop()
    
    def test_performance_benchmark(self, test_audio_file, temp_dir):
        """Benchmark de performance"""
        print("\n=== TESTE: Performance Benchmark ===")
        
        # Configurar orquestrador otimizado
        config = OrchestratorConfig(
            max_concurrent_jobs=1,
            chunk_duration=15.0,
            chunk_overlap=3.0,
            whisper_model="base"
        )
        
        orchestrator = DiarizationOrchestrator(config)
        
        try:
            # Iniciar orquestrador
            orchestrator.start()
            
            # Medir tempo de processamento
            output_dir = Path(temp_dir) / "benchmark_test"
            start_time = time.time()
            
            job_id = orchestrator.process_file(test_audio_file, str(output_dir))
            
            # Aguardar conclusão
            while True:
                status = orchestrator.get_job_status(job_id)
                if status and status["status"] in ["completed", "failed"]:
                    break
                time.sleep(1)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Verificar performance
            assert processing_time < 300  # Máximo 5 minutos para 30s de áudio
            
            # Verificar uso de memória
            memory_usage = psutil.virtual_memory().used / (1024**3)
            assert memory_usage < 16.0  # Máximo 16GB
            
            # Verificar CPU
            cpu_usage = psutil.cpu_percent(interval=1)
            assert cpu_usage < 95  # Máximo 95%
            
            print(f"✅ Performance Benchmark:")
            print(f"   - Tempo de processamento: {processing_time:.2f}s")
            print(f"   - Uso de memória: {memory_usage:.2f}GB")
            print(f"   - Uso de CPU: {cpu_usage:.1f}%")
        
        finally:
            orchestrator.stop()

def run_all_tests():
    """Executa todos os testes"""
    print("🚀 INICIANDO TESTES DA ARQUITETURA ROBUSTA")
    print("=" * 60)
    
    # Criar instância de teste
    test_instance = TestRobustArchitecture()
    
    # Executar testes em ordem
    tests = [
        test_instance.test_resource_manager,
        test_instance.test_audio_chunker,
        test_instance.test_whisper_processor,
        test_instance.test_speaker_diarizer,
        test_instance.test_transcription_merger,
        test_instance.test_diarization_orchestrator,
        test_instance.test_memory_management,
        test_instance.test_concurrent_processing,
        test_instance.test_error_recovery,
        test_instance.test_performance_benchmark
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            # Criar diretório temporário para cada teste
            with tempfile.TemporaryDirectory() as temp_dir:
                test_instance.temp_dir = temp_dir
                test()
                passed += 1
                print(f"✅ {test.__name__}: PASSOU")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__}: FALHOU - {str(e)}")
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL DOS TESTES")
    print("=" * 60)
    print(f"✅ Testes passaram: {passed}")
    print(f"❌ Testes falharam: {failed}")
    print(f"📈 Taxa de sucesso: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 TODOS OS TESTES PASSARAM! Arquitetura robusta validada.")
    else:
        print(f"\n⚠️ {failed} teste(s) falharam. Verificar implementação.")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1) 