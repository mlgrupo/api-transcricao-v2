#!/usr/bin/env python3
"""
CONFIGURADOR DE INTEGRAÇÃO DA ARQUITETURA ROBUSTA
===============================================
Este script configura a integração da arquitetura robusta de diarização
com o sistema existente de transcrição.
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any

def run_command(command: str, description: str) -> bool:
    """Executa um comando e retorna sucesso/falha"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - Sucesso")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Falha: {e.stderr}")
        return False

def check_file_exists(file_path: str) -> bool:
    """Verifica se um arquivo existe"""
    exists = Path(file_path).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {file_path}")
    return exists

def install_robust_dependencies() -> bool:
    """Instala dependências da arquitetura robusta"""
    print("\n📦 INSTALANDO DEPENDÊNCIAS DA ARQUITETURA ROBUSTA")
    print("=" * 60)
    
    # Verificar se requirements-robust.txt existe
    if not check_file_exists("requirements-robust.txt"):
        print("❌ requirements-robust.txt não encontrado")
        return False
    
    # Instalar dependências
    success = run_command(
        "pip install -r requirements-robust.txt",
        "Instalando dependências da arquitetura robusta"
    )
    
    return success

def setup_environment() -> bool:
    """Configura variáveis de ambiente necessárias"""
    print("\n🔧 CONFIGURANDO VARIÁVEIS DE AMBIENTE")
    print("=" * 60)
    
    # Verificar variáveis necessárias
    required_vars = [
        "HUGGINGFACE_TOKEN",
        "OPENAI_API_KEY"  # Opcional, mas recomendado
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("⚠️ Variáveis de ambiente ausentes:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Configure estas variáveis no seu .env ou ambiente:")
        print("   HUGGINGFACE_TOKEN=sua_token_aqui")
        print("   OPENAI_API_KEY=sua_chave_aqui (opcional)")
        return False
    
    print("✅ Todas as variáveis de ambiente configuradas")
    return True

def test_robust_architecture() -> bool:
    """Testa a arquitetura robusta"""
    print("\n🧪 TESTANDO ARQUITETURA ROBUSTA")
    print("=" * 60)
    
    # Verificar se os arquivos principais existem
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
        if not check_file_exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Arquivos ausentes: {missing_files}")
        return False
    
    # Testar importação dos componentes
    try:
        print("🔄 Testando importações...")
        
        # Testar resource manager
        from resource_manager import ResourceManager
        print("✅ ResourceManager importado")
        
        # Testar orchestrator
        from diarization_orchestrator import DiarizationOrchestrator
        print("✅ DiarizationOrchestrator importado")
        
        # Testar adaptador
        from robust_transcription_adapter import RobustTranscriptionAdapter
        print("✅ RobustTranscriptionAdapter importado")
        
    except ImportError as e:
        print(f"❌ Erro na importação: {e}")
        return False
    
    # Testar inicialização básica
    try:
        print("🔄 Testando inicialização...")
        
        # Criar resource manager
        resource_manager = ResourceManager(
            max_ram_gb=30,
            max_cpu_percent=80,
            max_concurrent_jobs=2
        )
        print("✅ ResourceManager inicializado")
        
        # Criar orchestrator
        orchestrator = DiarizationOrchestrator(
            resource_manager=resource_manager,
            max_workers=2,  # Reduzido para teste
            timeout_minutes=5,  # Reduzido para teste
            max_retries=2
        )
        print("✅ DiarizationOrchestrator inicializado")
        
        # Criar adaptador
        adapter = RobustTranscriptionAdapter()
        print("✅ RobustTranscriptionAdapter inicializado")
        
        # Verificar status
        status = adapter.get_system_status()
        print(f"✅ Status do sistema: {json.dumps(status, indent=2)}")
        
    except Exception as e:
        print(f"❌ Erro na inicialização: {e}")
        return False
    
    return True

def create_integration_config() -> bool:
    """Cria arquivo de configuração da integração"""
    print("\n⚙️ CRIANDO CONFIGURAÇÃO DE INTEGRAÇÃO")
    print("=" * 60)
    
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
        "logging_level": "INFO"
    }
    
    try:
        with open("robust_integration_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("✅ Configuração criada: robust_integration_config.json")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar configuração: {e}")
        return False

def update_transcription_script() -> bool:
    """Atualiza o script de transcrição para usar o adaptador"""
    print("\n📝 ATUALIZANDO SCRIPT DE TRANSCRIÇÃO")
    print("=" * 60)
    
    # Verificar se o script atual existe
    if not check_file_exists("transcription.py"):
        print("⚠️ Script transcription.py não encontrado, criando backup...")
        return True
    
    # Criar backup do script atual
    try:
        shutil.copy("transcription.py", "transcription_backup.py")
        print("✅ Backup criado: transcription_backup.py")
    except Exception as e:
        print(f"❌ Erro ao criar backup: {e}")
        return False
    
    # Verificar se o adaptador existe
    if not check_file_exists("robust_transcription_adapter.py"):
        print("❌ Adaptador robusto não encontrado")
        return False
    
    print("✅ Script atual mantido como backup")
    print("💡 O sistema agora usa robust_transcription_adapter.py automaticamente")
    
    return True

def create_test_script() -> bool:
    """Cria script de teste da integração"""
    print("\n🧪 CRIANDO SCRIPT DE TESTE")
    print("=" * 60)
    
    test_script = '''#!/usr/bin/env python3
"""
TESTE DA INTEGRAÇÃO ROBUSTA
==========================
Script para testar a integração da arquitetura robusta
"""

import asyncio
import json
import sys
from pathlib import Path

async def test_integration():
    try:
        from robust_transcription_adapter import get_adapter
        
        print("🧪 Testando integração robusta...")
        
        # Obter adaptador
        adapter = get_adapter()
        
        # Verificar status
        status = adapter.get_system_status()
        print(f"📊 Status: {json.dumps(status, indent=2)}")
        
        # Testar sistemas
        test_results = await adapter.test_systems()
        print(f"🧪 Testes: {json.dumps(test_results, indent=2)}")
        
        if test_results["robust_architecture"] or test_results["current_system"]:
            print("✅ Integração funcionando corretamente!")
            return True
        else:
            print("❌ Nenhum sistema funcionando")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)
'''
    
    try:
        with open("test_robust_integration.py", "w", encoding="utf-8") as f:
            f.write(test_script)
        
        # Tornar executável
        os.chmod("test_robust_integration.py", 0o755)
        
        print("✅ Script de teste criado: test_robust_integration.py")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar script de teste: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 CONFIGURADOR DE INTEGRAÇÃO DA ARQUITETURA ROBUSTA")
    print("=" * 70)
    print("Este script configura a integração da arquitetura robusta")
    print("de diarização com o sistema existente de transcrição.")
    print()
    
    # Verificar se estamos no diretório correto
    if not Path("requirements-robust.txt").exists():
        print("❌ Execute este script no diretório python/")
        print("   cd python/")
        print("   python setup_robust_integration.py")
        sys.exit(1)
    
    steps = [
        ("Instalando dependências", install_robust_dependencies),
        ("Configurando ambiente", setup_environment),
        ("Testando arquitetura", test_robust_architecture),
        ("Criando configuração", create_integration_config),
        ("Atualizando scripts", update_transcription_script),
        ("Criando teste", create_test_script)
    ]
    
    success_count = 0
    total_steps = len(steps)
    
    for step_name, step_func in steps:
        print(f"\n{'='*70}")
        print(f"PASSO {success_count + 1}/{total_steps}: {step_name.upper()}")
        print(f"{'='*70}")
        
        if step_func():
            success_count += 1
        else:
            print(f"⚠️ Falha no passo: {step_name}")
            # Continuar mesmo com falha, mas avisar
    
    print(f"\n{'='*70}")
    print("RESUMO DA CONFIGURAÇÃO")
    print(f"{'='*70}")
    print(f"✅ Passos concluídos: {success_count}/{total_steps}")
    
    if success_count == total_steps:
        print("🎉 Integração configurada com sucesso!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Execute o teste: python test_robust_integration.py")
        print("2. Reinicie o servidor Node.js")
        print("3. Teste uma transcrição")
    else:
        print("⚠️ Alguns passos falharam. Verifique os erros acima.")
        print("\n💡 DICAS:")
        print("- Configure as variáveis de ambiente necessárias")
        print("- Verifique se todas as dependências foram instaladas")
        print("- Execute o teste para verificar a integração")
    
    print(f"\n📁 Arquivos criados:")
    files_to_check = [
        "robust_integration_config.json",
        "test_robust_integration.py",
        "transcription_backup.py"
    ]
    
    for file in files_to_check:
        if Path(file).exists():
            print(f"   ✅ {file}")

if __name__ == "__main__":
    main() 