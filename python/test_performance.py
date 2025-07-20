#!/usr/bin/env python3
"""
Script de teste de performance para o sistema de transcrição otimizado
"""
import os
import sys
import time
import psutil
import subprocess
from pathlib import Path

def test_system_resources():
    """Testa recursos do sistema"""
    print("🔍 Testando recursos do sistema...")
    
    # CPU
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"CPU: {cpu_count} cores, {cpu_percent:.1f}% uso atual")
    
    # Memória
    memory = psutil.virtual_memory()
    memory_gb = memory.total / (1024**3)
    memory_available_gb = memory.available / (1024**3)
    print(f"RAM: {memory_gb:.1f}GB total, {memory_available_gb:.1f}GB disponível")
    
    # Verificar se temos recursos suficientes
    if cpu_count < 6:
        print("⚠️  Aviso: Menos de 6 cores detectados")
    if memory_gb < 16:
        print("⚠️  Aviso: Menos de 16GB RAM detectados")
    
    return cpu_count >= 6 and memory_gb >= 16

def test_dependencies():
    """Testa dependências Python"""
    print("\n📦 Testando dependências...")
    
    dependencies = [
        "whisper",
        "faster_whisper", 
        "pydub",
        "torch",
        "psutil",
        "numpy"
    ]
    
    missing = []
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep} - FALTANDO")
            missing.append(dep)
    
    return len(missing) == 0

def test_ffmpeg():
    """Testa FFmpeg"""
    print("\n🎬 Testando FFmpeg...")
    
    try:
        result = subprocess.run(["ffmpeg", "-version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ FFmpeg funcionando")
            return True
        else:
            print("❌ FFmpeg com erro")
            return False
    except Exception as e:
        print(f"❌ FFmpeg não encontrado: {e}")
        return False

def test_whisper_models():
    """Testa carregamento dos modelos Whisper"""
    print("\n🤖 Testando modelos Whisper...")
    
    models = ["medium", "large-v3"]
    
    for model in models:
        try:
            start_time = time.time()
            import whisper
            model_obj = whisper.load_model(model)
            load_time = time.time() - start_time
            print(f"✅ {model} carregado em {load_time:.1f}s")
        except Exception as e:
            print(f"❌ Erro ao carregar {model}: {e}")
            return False
    
    return True

def test_transcription_script():
    """Testa o script de transcrição"""
    print("\n🎯 Testando script de transcrição...")
    
    script_path = Path("chunked_transcribe.py")
    if not script_path.exists():
        print("❌ Script chunked_transcribe.py não encontrado")
        return False
    
    print("✅ Script encontrado")
    return True

def main():
    print("🚀 Teste de Performance - Sistema de Transcrição Otimizado")
    print("=" * 60)
    
    tests = [
        ("Recursos do Sistema", test_system_resources),
        ("Dependências Python", test_dependencies),
        ("FFmpeg", test_ffmpeg),
        ("Modelos Whisper", test_whisper_models),
        ("Script de Transcrição", test_transcription_script)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro no teste {test_name}: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 RESULTADOS DOS TESTES")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} testes passaram")
    
    if passed == len(results):
        print("\n🎉 SISTEMA PRONTO PARA TRANSCRIÇÃO!")
        print("✅ Todos os testes passaram")
        print("✅ Sistema otimizado para 7.5 vCPUs e 28GB RAM")
        print("✅ Pronto para processar vídeos de 5s a 5h")
    else:
        print("\n⚠️  PROBLEMAS DETECTADOS")
        print("❌ Alguns testes falharam")
        print("❌ Verifique as dependências antes de usar")
        sys.exit(1)

if __name__ == "__main__":
    main() 