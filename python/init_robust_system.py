#!/usr/bin/env python3
"""
INICIALIZADOR DO SISTEMA ROBUSTO
================================
Script que inicializa automaticamente toda a integração da arquitetura robusta
com o sistema existente de transcrição.
"""

import os
import sys
import json
import subprocess
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any

def print_banner():
    """Imprime banner do sistema"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    SISTEMA ROBUSTO DE DIARIZAÇÃO            ║
║                                                              ║
║  🚀 Arquitetura robusta para processamento simultâneo       ║
║  📊 Monitoramento de recursos em tempo real                ║
║  🎯 Diarização avançada com pyannote.audio                 ║
║  🔄 Fallback automático para sistema atual                 ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

def check_environment() -> Dict[str, Any]:
    """Verifica ambiente e dependências"""
    print("🔍 VERIFICANDO AMBIENTE")
    print("=" * 50)
    
    checks = {
        "python_version": sys.version_info >= (3, 8),
        "pip_available": False,
        "ffmpeg_available": False,
        "required_vars": [],
        "optional_vars": []
    }
    
    # Verificar versão do Python
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Verificar pip
    try:
        import pip
        checks["pip_available"] = True
        print("✅ pip disponível")
    except ImportError:
        print("❌ pip não disponível")
    
    # Verificar ffmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        checks["ffmpeg_available"] = result.returncode == 0
        if checks["ffmpeg_available"]:
            print("✅ ffmpeg disponível")
        else:
            print("❌ ffmpeg não disponível")
    except FileNotFoundError:
        print("❌ ffmpeg não encontrado")
    
    # Verificar variáveis de ambiente
    required_vars = ["HUGGINGFACE_TOKEN"]
    optional_vars = ["OPENAI_API_KEY"]
    
    for var in required_vars:
        if os.environ.get(var):
            checks["required_vars"].append(var)
            print(f"✅ {var} configurada")
        else:
            print(f"❌ {var} não configurada")
    
    for var in optional_vars:
        if os.environ.get(var):
            checks["optional_vars"].append(var)
            print(f"✅ {var} configurada (opcional)")
        else:
            print(f"⚠️ {var} não configurada (opcional)")
    
    return checks

def install_dependencies() -> bool:
    """Instala dependências necessárias"""
    print("\n📦 INSTALANDO DEPENDÊNCIAS")
    print("=" * 50)
    
    # Verificar se requirements-robust.txt existe
    if not Path("requirements-robust.txt").exists():
        print("❌ requirements-robust.txt não encontrado")
        return False
    
    try:
        # Instalar dependências
        print("🔄 Instalando dependências da arquitetura robusta...")
        result = subprocess.run(
            ["pip", "install", "-r", "requirements-robust.txt"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Dependências instaladas com sucesso")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar dependências: {e.stderr}")
        return False

def setup_robust_architecture() -> bool:
    """Configura a arquitetura robusta"""
    print("\n⚙️ CONFIGURANDO ARQUITETURA ROBUSTA")
    print("=" * 50)
    
    # Verificar se todos os arquivos necessários existem
    required_files = [
        "resource_manager.py",
        "audio_chunker.py",
        "whisper_processor.py", 
        "speaker_diarizer.py",
        "transcription_merger.py",
        "diarization_orchestrator.py",
        "robust_transcription_adapter.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
        else:
            print(f"✅ {file}")
    
    if missing_files:
        print(f"❌ Arquivos ausentes: {missing_files}")
        return False
    
    # Testar importações
    try:
        print("\n🔄 Testando importações...")
        
        from resource_manager import ResourceManager
        from diarization_orchestrator import DiarizationOrchestrator
        from robust_transcription_adapter import RobustTranscriptionAdapter
        
        print("✅ Todas as importações funcionando")
        
        # Testar inicialização básica
        print("🔄 Testando inicialização...")
        
        resource_manager = ResourceManager(
            max_ram_gb=30,
            max_cpu_percent=80,
            max_concurrent_jobs=2
        )
        
        orchestrator = DiarizationOrchestrator(
            resource_manager=resource_manager,
            max_workers=2,
            timeout_minutes=5,
            max_retries=2
        )
        
        adapter = RobustTranscriptionAdapter()
        
        print("✅ Inicialização bem-sucedida")
        return True
        
    except Exception as e:
        print(f"❌ Erro na configuração: {e}")
        return False

def create_configuration() -> bool:
    """Cria arquivo de configuração"""
    print("\n📝 CRIANDO CONFIGURAÇÃO")
    print("=" * 50)
    
    config = {
        "integration_version": "1.0.0",
        "robust_architecture_enabled": True,
        "fallback_to_current_system": True,
        "resource_limits": {
            "max_ram_gb": 30,
            "max_cpu_percent": 80,
            "max_concurrent_jobs": 2
        },
        "processing_config": {
            "max_workers": 4,
            "timeout_minutes": 10,
            "max_retries": 3,
            "chunk_duration_seconds": 30,
            "chunk_overlap_seconds": 5
        },
        "diarization_config": {
            "max_speakers": 6,
            "min_speaker_duration": 1.0,
            "speaker_consistency_threshold": 0.7
        },
        "output_formats": ["json", "srt", "txt"],
        "logging_level": "INFO",
        "auto_fallback": True,
        "performance_monitoring": True
    }
    
    try:
        with open("robust_integration_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("✅ Configuração criada: robust_integration_config.json")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar configuração: {e}")
        return False

async def test_system() -> bool:
    """Testa o sistema completo"""
    print("\n🧪 TESTANDO SISTEMA")
    print("=" * 50)
    
    try:
        from robust_transcription_adapter import get_adapter
        
        adapter = get_adapter()
        
        # Verificar status
        status = adapter.get_system_status()
        print(f"📊 Status do sistema: {json.dumps(status, indent=2)}")
        
        # Testar sistemas
        test_results = await adapter.test_systems()
        print(f"🧪 Resultados dos testes: {json.dumps(test_results, indent=2)}")
        
        if test_results["robust_architecture"] or test_results["current_system"]:
            print("✅ Sistema funcionando corretamente!")
            return True
        else:
            print("❌ Nenhum sistema funcionando")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

def create_startup_script() -> bool:
    """Cria script de inicialização"""
    print("\n🚀 CRIANDO SCRIPT DE INICIALIZAÇÃO")
    print("=" * 50)
    
    startup_script = '''#!/usr/bin/env python3
"""
SCRIPT DE INICIALIZAÇÃO DO SISTEMA ROBUSTO
=========================================
Execute este script para inicializar o sistema robusto de diarização
"""

import sys
import os
from pathlib import Path

def main():
    # Adicionar diretório atual ao path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    
    try:
        from robust_transcription_adapter import get_adapter
        import asyncio
        
        print("🚀 Inicializando sistema robusto...")
        
        # Obter adaptador
        adapter = get_adapter()
        
        # Verificar status
        status = adapter.get_system_status()
        print(f"📊 Status: {status}")
        
        if status.get("using_robust_architecture"):
            print("✅ Sistema robusto ativo")
        else:
            print("📊 Usando sistema atual como fallback")
        
        print("🎯 Sistema pronto para uso!")
        
    except Exception as e:
        print(f"❌ Erro na inicialização: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    
    try:
        with open("start_robust_system.py", "w", encoding="utf-8") as f:
            f.write(startup_script)
        
        # Tornar executável
        os.chmod("start_robust_system.py", 0o755)
        
        print("✅ Script de inicialização criado: start_robust_system.py")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar script: {e}")
        return False

def create_documentation() -> bool:
    """Cria documentação da integração"""
    print("\n📚 CRIANDO DOCUMENTAÇÃO")
    print("=" * 50)
    
    docs = """# INTEGRAÇÃO DA ARQUITETURA ROBUSTA

## Visão Geral
Este sistema integra uma arquitetura robusta de diarização com o sistema existente de transcrição.

## Componentes
- **ResourceManager**: Gerencia recursos do sistema (RAM, CPU)
- **AudioChunker**: Divide áudio em chunks otimizados
- **WhisperProcessor**: Processa transcrição com Whisper
- **SpeakerDiarizer**: Identifica speakers usando pyannote.audio
- **TranscriptionMerger**: Combina transcrição e diarização
- **DiarizationOrchestrator**: Orquestra todo o processo
- **RobustTranscriptionAdapter**: Adaptador para integração

## Configuração
1. Configure as variáveis de ambiente:
   - HUGGINGFACE_TOKEN (obrigatório)
   - OPENAI_API_KEY (opcional)

2. Execute o script de configuração:
   ```bash
   python setup_robust_integration.py
   ```

3. Teste o sistema:
   ```bash
   python test_robust_integration.py
   ```

## Uso
O sistema é usado automaticamente pelo TranscriptionProcessor do Node.js.
Ele escolhe automaticamente entre a arquitetura robusta e o sistema atual.

## Monitoramento
- Use `/api/robust/status` para verificar status
- Use `/api/robust/metrics` para métricas de recursos
- Use `/api/robust/logs` para logs do sistema

## Troubleshooting
1. Verifique se todas as dependências estão instaladas
2. Configure as variáveis de ambiente necessárias
3. Execute os testes para verificar funcionamento
4. Verifique os logs para identificar problemas
"""
    
    try:
        with open("ROBUST_INTEGRATION_README.md", "w", encoding="utf-8") as f:
            f.write(docs)
        
        print("✅ Documentação criada: ROBUST_INTEGRATION_README.md")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar documentação: {e}")
        return False

async def main():
    """Função principal"""
    print_banner()
    
    # Verificar se estamos no diretório correto
    if not Path("requirements-robust.txt").exists():
        print("❌ Execute este script no diretório python/")
        print("   cd python/")
        print("   python init_robust_system.py")
        sys.exit(1)
    
    # Executar etapas
    steps = [
        ("Verificando ambiente", lambda: check_environment()),
        ("Instalando dependências", install_dependencies),
        ("Configurando arquitetura", setup_robust_architecture),
        ("Criando configuração", create_configuration),
        ("Testando sistema", lambda: asyncio.run(test_system())),
        ("Criando script de inicialização", create_startup_script),
        ("Criando documentação", create_documentation)
    ]
    
    success_count = 0
    total_steps = len(steps)
    
    for step_name, step_func in steps:
        print(f"\n{'='*70}")
        print(f"PASSO {success_count + 1}/{total_steps}: {step_name.upper()}")
        print(f"{'='*70}")
        
        try:
            if step_func():
                success_count += 1
            else:
                print(f"⚠️ Falha no passo: {step_name}")
        except Exception as e:
            print(f"❌ Erro no passo {step_name}: {e}")
    
    # Resumo final
    print(f"\n{'='*70}")
    print("RESUMO DA INICIALIZAÇÃO")
    print(f"{'='*70}")
    print(f"✅ Passos concluídos: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("🎉 Sistema robusto inicializado com sucesso!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Reinicie o servidor Node.js")
        print("2. Teste uma transcrição")
        print("3. Monitore os recursos em /api/robust/metrics")
        print("4. Verifique logs em /api/robust/logs")
    else:
        print("⚠️ Alguns passos falharam. Verifique os erros acima.")
        print("\n💡 DICAS:")
        print("- Configure as variáveis de ambiente necessárias")
        print("- Verifique se todas as dependências foram instaladas")
        print("- Execute o teste para verificar a integração")
    
    print(f"\n📁 Arquivos criados:")
    files_to_check = [
        "robust_integration_config.json",
        "start_robust_system.py",
        "ROBUST_INTEGRATION_README.md"
    ]
    
    for file in files_to_check:
        if Path(file).exists():
            print(f"   ✅ {file}")

if __name__ == "__main__":
    asyncio.run(main()) 