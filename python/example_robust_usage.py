#!/usr/bin/env python3
"""
Exemplo de Uso da Arquitetura Robusta
Demonstra diferentes cenários de uso da arquitetura de diarização
"""

import os
import time
import tempfile
from pathlib import Path
import structlog

# Importar componentes
from diarization_orchestrator import DiarizationOrchestrator, OrchestratorConfig
from resource_manager import JobPriority

# Configurar logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

def example_single_file_processing():
    """Exemplo: Processamento de arquivo único"""
    print("\n🎯 EXEMPLO 1: Processamento de Arquivo Único")
    print("=" * 50)
    
    # Configurar orquestrador para arquivo único
    config = OrchestratorConfig(
        max_concurrent_jobs=1,
        chunk_duration=30.0,
        chunk_overlap=5.0,
        whisper_model="large-v3",
        max_speakers=8
    )
    
    # Criar diretório temporário para exemplo
    with tempfile.TemporaryDirectory() as temp_dir:
        # Simular arquivo de áudio (você substituiria pelo caminho real)
        audio_file = "caminho/para/seu/audio.mp4"  # Substitua pelo arquivo real
        
        if not os.path.exists(audio_file):
            print(f"⚠️ Arquivo não encontrado: {audio_file}")
            print("   Crie um arquivo de áudio para testar ou modifique o caminho")
            return
        
        output_dir = Path(temp_dir) / "single_file_output"
        
        print(f"📁 Arquivo de entrada: {audio_file}")
        print(f"📁 Diretório de saída: {output_dir}")
        
        # Processar com orquestrador
        with DiarizationOrchestrator(config) as orchestrator:
            # Submeter job
            job_id = orchestrator.process_file(audio_file, str(output_dir))
            print(f"🆔 Job ID: {job_id}")
            
            # Monitorar progresso
            while True:
                status = orchestrator.get_job_status(job_id)
                if status:
                    progress = status.get("progress", {})
                    print(f"📊 Progresso: {progress.get('percent', 0)}% - {progress.get('message', 'Processando...')}")
                    
                    if status["status"] in ["completed", "failed"]:
                        break
                
                time.sleep(5)
            
            # Verificar resultado
            if status["status"] == "completed":
                print("✅ Processamento concluído com sucesso!")
                
                # Listar arquivos de saída
                output_files = list(output_dir.glob("*"))
                print("📄 Arquivos gerados:")
                for file in output_files:
                    print(f"   - {file.name}")
                
                # Mostrar estatísticas
                system_status = orchestrator.get_system_status()
                print(f"📈 Estatísticas:")
                print(f"   - Jobs processados: {system_status['orchestrator_stats']['total_jobs_processed']}")
                print(f"   - Tempo médio: {system_status['orchestrator_stats']['average_processing_time']:.2f}s")
            else:
                print(f"❌ Processamento falhou: {status.get('error', 'Erro desconhecido')}")

def example_concurrent_processing():
    """Exemplo: Processamento concorrente de múltiplos arquivos"""
    print("\n🎯 EXEMPLO 2: Processamento Concorrente")
    print("=" * 50)
    
    # Configurar orquestrador para processamento concorrente
    config = OrchestratorConfig(
        max_concurrent_jobs=2,  # Processar 2 arquivos simultaneamente
        chunk_duration=30.0,
        chunk_overlap=5.0,
        whisper_model="large-v3",
        max_speakers=8
    )
    
    # Lista de arquivos para processar (substitua pelos caminhos reais)
    audio_files = [
        "caminho/para/audio1.mp4",
        "caminho/para/audio2.mp4",
        "caminho/para/audio3.mp4"
    ]
    
    # Filtrar arquivos existentes
    existing_files = [f for f in audio_files if os.path.exists(f)]
    
    if not existing_files:
        print("⚠️ Nenhum arquivo encontrado para processamento")
        print("   Modifique a lista 'audio_files' com caminhos válidos")
        return
    
    print(f"📁 Arquivos para processar: {len(existing_files)}")
    for file in existing_files:
        print(f"   - {file}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with DiarizationOrchestrator(config) as orchestrator:
            # Submeter todos os jobs
            job_ids = []
            for i, audio_file in enumerate(existing_files):
                output_dir = Path(temp_dir) / f"concurrent_output_{i}"
                job_id = orchestrator.process_file(audio_file, str(output_dir))
                job_ids.append(job_id)
                print(f"🆔 Job {i+1} ID: {job_id}")
            
            # Monitorar progresso de todos os jobs
            completed_jobs = 0
            start_time = time.time()
            
            while completed_jobs < len(job_ids):
                completed_jobs = 0
                
                for i, job_id in enumerate(job_ids):
                    status = orchestrator.get_job_status(job_id)
                    if status:
                        progress = status.get("progress", {})
                        print(f"📊 Job {i+1}: {progress.get('percent', 0)}% - {progress.get('message', 'Processando...')}")
                        
                        if status["status"] in ["completed", "failed"]:
                            completed_jobs += 1
                
                if completed_jobs < len(job_ids):
                    print(f"⏳ Aguardando... ({completed_jobs}/{len(job_ids)} completados)")
                    time.sleep(10)
            
            # Relatório final
            total_time = time.time() - start_time
            print(f"\n✅ Processamento concorrente concluído em {total_time:.2f}s")
            
            # Estatísticas finais
            system_status = orchestrator.get_system_status()
            print(f"📈 Estatísticas finais:")
            print(f"   - Jobs processados: {system_status['orchestrator_stats']['total_jobs_processed']}")
            print(f"   - Jobs bem-sucedidos: {system_status['orchestrator_stats']['successful_jobs']}")
            print(f"   - Jobs falharam: {system_status['orchestrator_stats']['failed_jobs']}")
            print(f"   - Tempo médio por job: {system_status['orchestrator_stats']['average_processing_time']:.2f}s")

def example_priority_processing():
    """Exemplo: Processamento com prioridades"""
    print("\n🎯 EXEMPLO 3: Processamento com Prioridades")
    print("=" * 50)
    
    config = OrchestratorConfig(
        max_concurrent_jobs=1,  # Processar um por vez para demonstrar prioridades
        chunk_duration=30.0,
        chunk_overlap=5.0,
        whisper_model="large-v3"
    )
    
    # Lista de arquivos com diferentes prioridades
    files_with_priority = [
        ("caminho/para/audio_baixa_prioridade.mp4", JobPriority.LOW),
        ("caminho/para/audio_alta_prioridade.mp4", JobPriority.HIGH),
        ("caminho/para/audio_normal.mp4", JobPriority.NORMAL)
    ]
    
    # Filtrar arquivos existentes
    existing_files = [(f, p) for f, p in files_with_priority if os.path.exists(f)]
    
    if not existing_files:
        print("⚠️ Nenhum arquivo encontrado para processamento")
        return
    
    print("📁 Arquivos com prioridades:")
    for file, priority in existing_files:
        print(f"   - {file} (Prioridade: {priority.name})")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with DiarizationOrchestrator(config) as orchestrator:
            # Submeter jobs com prioridades
            job_ids = []
            for i, (audio_file, priority) in enumerate(existing_files):
                output_dir = Path(temp_dir) / f"priority_output_{i}"
                job_id = orchestrator.submit_job(audio_file, str(output_dir), priority)
                job_ids.append(job_id)
                print(f"🆔 Job {i+1} (Prioridade: {priority.name}) ID: {job_id}")
            
            # Monitorar processamento
            completed_jobs = 0
            while completed_jobs < len(job_ids):
                for i, job_id in enumerate(job_ids):
                    status = orchestrator.get_job_status(job_id)
                    if status and status["status"] in ["completed", "failed"]:
                        completed_jobs += 1
                        priority_name = existing_files[i][1].name
                        print(f"✅ Job {i+1} ({priority_name}) {status['status']}")
                
                if completed_jobs < len(job_ids):
                    time.sleep(5)
            
            print("✅ Processamento com prioridades concluído!")

def example_monitoring_and_metrics():
    """Exemplo: Monitoramento e métricas em tempo real"""
    print("\n🎯 EXEMPLO 4: Monitoramento e Métricas")
    print("=" * 50)
    
    config = OrchestratorConfig(
        max_concurrent_jobs=2,
        enable_monitoring=True,
        log_interval=10  # Log a cada 10 segundos
    )
    
    # Simular arquivo (substitua pelo caminho real)
    audio_file = "caminho/para/audio_monitoramento.mp4"
    
    if not os.path.exists(audio_file):
        print(f"⚠️ Arquivo não encontrado: {audio_file}")
        return
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with DiarizationOrchestrator(config) as orchestrator:
            # Submeter job
            output_dir = Path(temp_dir) / "monitoring_output"
            job_id = orchestrator.process_file(audio_file, str(output_dir))
            
            print(f"🆔 Job ID: {job_id}")
            print("📊 Monitoramento em tempo real:")
            
            # Monitorar por 60 segundos ou até completar
            start_time = time.time()
            while time.time() - start_time < 60:
                # Status do job
                job_status = orchestrator.get_job_status(job_id)
                if job_status and job_status["status"] in ["completed", "failed"]:
                    print(f"✅ Job {job_status['status']}")
                    break
                
                # Status do sistema
                system_status = orchestrator.get_system_status()
                resource_status = system_status["resource_manager"]
                
                print(f"⏰ {time.strftime('%H:%M:%S')} - "
                      f"RAM: {resource_status['memory']['used_gb']:.1f}GB "
                      f"CPU: {resource_status['cpu']['percent']:.1f}% "
                      f"Jobs ativos: {system_status['active_jobs']}")
                
                time.sleep(10)
            
            # Relatório final
            final_status = orchestrator.get_system_status()
            print(f"\n📈 Relatório Final:")
            print(f"   - Pico de memória: {final_status['orchestrator_stats']['peak_memory_usage']:.2f}GB")
            print(f"   - Jobs processados: {final_status['orchestrator_stats']['total_jobs_processed']}")
            print(f"   - Tempo total: {final_status['orchestrator_stats']['total_processing_time']:.2f}s")

def example_error_handling():
    """Exemplo: Tratamento de erros"""
    print("\n🎯 EXEMPLO 5: Tratamento de Erros")
    print("=" * 50)
    
    config = OrchestratorConfig(
        max_concurrent_jobs=1,
        enable_recovery=True
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Criar arquivo inválido para testar tratamento de erro
        invalid_file = Path(temp_dir) / "invalid_audio.txt"
        with open(invalid_file, 'w') as f:
            f.write("Este não é um arquivo de áudio válido")
        
        with DiarizationOrchestrator(config) as orchestrator:
            # Submeter job com arquivo inválido
            output_dir = Path(temp_dir) / "error_test_output"
            job_id = orchestrator.process_file(str(invalid_file), str(output_dir))
            
            print(f"🆔 Job ID: {job_id}")
            print("⚠️ Processando arquivo inválido para testar tratamento de erro...")
            
            # Aguardar conclusão
            while True:
                status = orchestrator.get_job_status(job_id)
                if status and status["status"] in ["completed", "failed"]:
                    break
                time.sleep(5)
            
            # Verificar tratamento de erro
            if status["status"] == "failed":
                print("✅ Tratamento de erro funcionou corretamente!")
                print(f"   Erro: {status.get('error', 'Erro desconhecido')}")
                
                # Verificar se o sistema continua funcionando
                system_status = orchestrator.get_system_status()
                print(f"   Sistema continua funcionando: {system_status['active_jobs']} jobs ativos")
            else:
                print("❌ Erro não foi tratado corretamente")

def main():
    """Função principal com menu de exemplos"""
    print("🎯 ARQUITETURA ROBUSTA DE DIARIZAÇÃO")
    print("=" * 50)
    print("Exemplos de uso disponíveis:")
    print("1. Processamento de arquivo único")
    print("2. Processamento concorrente")
    print("3. Processamento com prioridades")
    print("4. Monitoramento e métricas")
    print("5. Tratamento de erros")
    print("6. Executar todos os exemplos")
    print("0. Sair")
    
    while True:
        try:
            choice = input("\nEscolha um exemplo (0-6): ").strip()
            
            if choice == "0":
                print("👋 Saindo...")
                break
            elif choice == "1":
                example_single_file_processing()
            elif choice == "2":
                example_concurrent_processing()
            elif choice == "3":
                example_priority_processing()
            elif choice == "4":
                example_monitoring_and_metrics()
            elif choice == "5":
                example_error_handling()
            elif choice == "6":
                print("\n🚀 Executando todos os exemplos...")
                example_single_file_processing()
                example_concurrent_processing()
                example_priority_processing()
                example_monitoring_and_metrics()
                example_error_handling()
                print("\n✅ Todos os exemplos executados!")
            else:
                print("❌ Opção inválida. Escolha 0-6.")
        
        except KeyboardInterrupt:
            print("\n👋 Interrompido pelo usuário.")
            break
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main() 