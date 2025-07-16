#!/usr/bin/env python3
"""
Script de teste para verificar a transcrição
"""

import sys
import os
import json
from pathlib import Path

def test_imports():
    """Testa se as dependências estão funcionando"""
    print("🔍 Testando importações...")
    
    try:
        import whisper
        print("✅ Whisper importado com sucesso")
    except ImportError as e:
        print(f"❌ Erro ao importar Whisper: {e}")
        return False
    
    try:
        from pydub import AudioSegment
        print("✅ Pydub importado com sucesso")
    except ImportError as e:
        print(f"❌ Erro ao importar Pydub: {e}")
        return False
    
    try:
        import numpy as np
        print("✅ NumPy importado com sucesso")
    except ImportError as e:
        print(f"❌ Erro ao importar NumPy: {e}")
        return False
    
    return True

def test_whisper_model():
    """Testa se o modelo Whisper pode ser carregado"""
    print("\n🤖 Testando carregamento do modelo Whisper...")
    
    try:
        import whisper
        model = whisper.load_model("tiny")  # Modelo pequeno para teste rápido
        print("✅ Modelo Whisper carregado com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao carregar modelo Whisper: {e}")
        return False

def test_audio_processing():
    """Testa processamento de áudio"""
    print("\n🎵 Testando processamento de áudio...")
    
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        
        # Criar áudio de teste simples
        tone = Sine(440).to_audio_segment(duration=1000)  # 1 segundo de tom
        print("✅ Processamento de áudio funcionando")
        return True
    except Exception as e:
        print(f"❌ Erro no processamento de áudio: {e}")
        return False

def test_transcription_script():
    """Testa se o script de transcrição existe e pode ser executado"""
    print("\n📝 Testando script de transcrição...")
    
    script_path = Path("transcribe.py")
    if not script_path.exists():
        print("❌ Script transcribe.py não encontrado")
        return False
    
    print("✅ Script transcribe.py encontrado")
    return True

def main():
    """Função principal"""
    print("🧪 Teste do Sistema de Transcrição")
    print("=" * 40)
    
    tests = [
        ("Importações", test_imports),
        ("Modelo Whisper", test_whisper_model),
        ("Processamento de Áudio", test_audio_processing),
        ("Script de Transcrição", test_transcription_script)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"Teste: {test_name}")
        print(f"{'='*40}")
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} - PASSOU")
        else:
            print(f"❌ {test_name} - FALHOU")
    
    print(f"\n{'='*40}")
    print(f"RESULTADO: {passed}/{total} testes passaram")
    print(f"{'='*40}")
    
    if passed == total:
        print("🎉 Sistema pronto para transcrição!")
        print("\n📋 Para testar com um arquivo de áudio:")
        print("   python transcribe.py caminho/para/audio.mp3")
        return 0
    else:
        print("⚠️ Alguns testes falharam. Verifique as dependências.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 