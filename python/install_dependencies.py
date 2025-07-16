#!/usr/bin/env python3
"""
Script de instalação automática de dependências para o sistema de transcrição
Versão compatível com Windows
"""

import subprocess
import sys
import os
import platform
from pathlib import Path

def run_command(command, description):
    """Executa um comando e retorna o resultado"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            check=True
        )
        print(f"✅ {description} concluído")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro em {description}: {e}")
        print(f"   Comando: {command}")
        print(f"   Erro: {e.stderr}")
        return False, e.stderr

def check_python_version():
    """Verifica se a versão do Python é compatível"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ é necessário")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detectado")
    return True

def install_pip_package(package, version=None):
    """Instala um pacote pip com fallback"""
    if version:
        package_spec = f"{package}=={version}"
    else:
        package_spec = package
    
    success, output = run_command(
        f"pip install {package_spec}",
        f"Instalando {package_spec}"
    )
    
    if not success:
        # Tentar sem versão específica
        if version:
            print(f"🔄 Tentando instalar {package} sem versão específica...")
            success, output = run_command(
                f"pip install {package}",
                f"Instalando {package} (sem versão)"
            )
    
    return success

def install_system_dependencies():
    """Instala dependências do sistema"""
    system = platform.system().lower()
    
    if system == "windows":
        print("🔄 Verificando dependências do Windows...")
        
        # Verificar se o Visual C++ Build Tools está instalado
        try:
            result = subprocess.run(
                "where cl.exe", 
                shell=True, 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                print("✅ Visual C++ Build Tools detectado")
            else:
                print("⚠️  Visual C++ Build Tools não encontrado")
                print("   Algumas bibliotecas podem falhar na compilação")
                print("   Instale em: https://visualstudio.microsoft.com/visual-cpp-build-tools/")
        except:
            pass
    
    elif system == "linux":
        print("🔄 Instalando dependências do sistema Linux...")
        run_command("sudo apt-get update", "Atualizando repositórios")
        run_command(
            "sudo apt-get install -y ffmpeg portaudio19-dev python3-dev build-essential",
            "Instalando dependências do sistema"
        )
    
    elif system == "darwin":  # macOS
        print("🔄 Verificando dependências do macOS...")
        run_command("brew install ffmpeg portaudio", "Instalando dependências via Homebrew")

def install_python_packages():
    """Instala pacotes Python"""
    print("\n📦 Instalando pacotes Python...")
    
    # Dependências principais (mais estáveis)
    core_packages = [
        ("openai-whisper", "20231117"),
        ("pydub", "0.25.1"),
        ("numpy", "1.24.3"),
        ("python-dotenv", "1.0.0"),
        ("requests", "2.31.0"),
        ("spellchecker", "0.7.2")
    ]
    
    for package, version in core_packages:
        install_pip_package(package, version)
    
    # Dependências que podem ser problemáticas
    problematic_packages = [
        ("librosa", "0.10.1"),
        ("noisereduce", "3.0.0"),
        ("spacy", "3.7.2")
    ]
    
    for package, version in problematic_packages:
        success = install_pip_package(package, version)
        if not success:
            print(f"⚠️  {package} falhou na instalação - tentando sem versão específica")
            install_pip_package(package)

def download_spacy_model():
    """Baixa modelo do spaCy"""
    print("\n🤖 Baixando modelo do spaCy...")
    success, output = run_command(
        "python -m spacy download pt_core_news_sm",
        "Baixando modelo português do spaCy"
    )
    
    if not success:
        print("⚠️  Modelo spaCy não pôde ser baixado")
        print("   O processamento de texto pode ser limitado")

def verify_installation():
    """Verifica se a instalação foi bem-sucedida"""
    print("\n🔍 Verificando instalação...")
    
    test_imports = [
        "whisper",
        "pydub", 
        "numpy",
        "librosa",
        "noisereduce",
        "spellchecker"
    ]
    
    failed_imports = []
    
    for module in test_imports:
        try:
            __import__(module)
            print(f"✅ {module} - OK")
        except ImportError as e:
            print(f"❌ {module} - FALHOU: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n⚠️  {len(failed_imports)} módulos falharam na importação:")
        for module in failed_imports:
            print(f"   - {module}")
        return False
    
    print("\n🎉 Todas as dependências foram instaladas com sucesso!")
    return True

def main():
    """Função principal"""
    print("🚀 Instalador de Dependências - Sistema de Transcrição")
    print("=" * 50)
    
    # Verificar Python
    if not check_python_version():
        sys.exit(1)
    
    # Instalar dependências do sistema
    install_system_dependencies()
    
    # Instalar pacotes Python
    install_python_packages()
    
    # Baixar modelo spaCy
    download_spacy_model()
    
    # Verificar instalação
    success = verify_installation()
    
    if success:
        print("\n✨ Instalação concluída com sucesso!")
        print("   Você pode agora executar o sistema de transcrição.")
    else:
        print("\n⚠️  Algumas dependências falharam na instalação.")
        print("   Verifique os erros acima e tente novamente.")
        sys.exit(1)

if __name__ == "__main__":
    main() 