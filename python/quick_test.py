#!/usr/bin/env python3
"""
Teste rápido do sistema avançado de transcrição
"""

import sys
import os
import tempfile
import json
from pathlib import Path

def test_imports():
    """Testa se todas as dependências estão disponíveis"""
    print("🧪 Testando importações...")
    
    try:
        import whisper
        import pydub
        import numpy as np
        import librosa
        import noisereduce as nr
        # import webrtcvad  # Removido - não disponível no Windows
        from spellchecker import SpellChecker
        import spacy
        import torch
        
        print("✅ Todas as dependências importadas com sucesso")
        return True
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        return False

def test_whisper_model():
    """Testa carregamento do modelo Whisper"""
    print("🎤 Testando modelo Whisper...")
    
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
    print("🎵 Testando processamento de áudio...")
    
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        
        # Criar áudio de teste
        tone = Sine(440).to_audio_segment(duration=1000)
        
        # Testar normalização
        normalized = tone.normalize()
        
        print("✅ Processamento de áudio funcionando")
        return True
    except Exception as e:
        print(f"❌ Erro no processamento de áudio: {e}")
        return False

def test_transcription_system():
    """Testa o sistema de transcrição"""
    print("🎤 Testando sistema de transcrição...")
    
    try:
        # Importar módulos do sistema
        from transcribe import TranscriptionConfig, ParallelTranscriptionProcessor
        
        # Configuração de teste
        config = TranscriptionConfig(
            chunk_duration_ms=30 * 1000,  # 30 segundos
            max_workers=2,
            max_memory_chunks=2,
            noise_reduction=False,  # Desabilitar para teste rápido
            silence_removal=False,
            spell_check=False
        )
        
        # Criar processador
        processor = ParallelTranscriptionProcessor(config)
        
        print("✅ Sistema de transcrição inicializado")
        return True
    except Exception as e:
        print(f"❌ Erro no sistema de transcrição: {e}")
        return False

def test_context_detection():
    """Testa detecção de contexto"""
    print("🧠 Testando detecção de contexto...")
    
    try:
        from transcribe import ContextDetector
        
        detector = ContextDetector()
        
        # Testar diferentes contextos
        test_files = [
            "reuniao_equipe.mp3",
            "entrevista_politico.mp3", 
            "palestra_universidade.mp3",
            "podcast_tecnologia.mp3",
            "audio_generico.mp3"
        ]
        
        for filename in test_files:
            context = detector.detect_context(filename)
            print(f"   {filename} -> {context}")
        
        print("✅ Detecção de contexto funcionando")
        return True
    except Exception as e:
        print(f"❌ Erro na detecção de contexto: {e}")
        return False

def test_post_processing():
    """Testa pós-processamento"""
    print("✨ Testando pós-processamento...")
    
    try:
        from transcribe import TranscriptionConfig, IntelligentPostProcessor
        
        config = TranscriptionConfig(spell_check=True)
        processor = IntelligentPostProcessor(config)
        
        # Texto de teste
        test_text = "olá, como vc está? tá tudo bem né? vamo fazê isso"
        
        # Processar
        processed = processor.process(test_text)
        
        print(f"   Original: {test_text}")
        print(f"   Processado: {processed}")
        
        print("✅ Pós-processamento funcionando")
        return True
    except Exception as e:
        print(f"❌ Erro no pós-processamento: {e}")
        return False

def create_test_audio():
    """Cria áudio de teste"""
    print("🎵 Criando áudio de teste...")
    
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        
        # Criar tom de teste
        tone = Sine(440).to_audio_segment(duration=5000)  # 5 segundos
        
        # Salvar arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        tone.export(temp_file.name, format='mp3')
        
        print(f"✅ Áudio de teste criado: {temp_file.name}")
        return temp_file.name
    except Exception as e:
        print(f"❌ Erro ao criar áudio de teste: {e}")
        return None

def test_full_transcription():
    """Testa transcrição completa"""
    print("🎤 Testando transcrição completa...")
    
    try:
        # Criar áudio de teste
        audio_file = create_test_audio()
        if not audio_file:
            return False
        
        # Importar e configurar
        from transcribe import TranscriptionConfig, ParallelTranscriptionProcessor
        
        config = TranscriptionConfig(
            chunk_duration_ms=30 * 1000,
            max_workers=1,
            max_memory_chunks=1,
            noise_reduction=False,
            silence_removal=False,
            spell_check=False
        )
        
        processor = ParallelTranscriptionProcessor(config)
        
        # Executar transcrição
        result = processor.transcribe(audio_file)
        
        print(f"✅ Transcrição concluída: {len(result)} caracteres")
        
        # Limpar arquivo temporário
        os.unlink(audio_file)
        
        return True
    except Exception as e:
        print(f"❌ Erro na transcrição completa: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 Teste Rápido do Sistema Avançado de Transcrição")
    print("=" * 60)
    
    tests = [
        ("Importações", test_imports),
        ("Modelo Whisper", test_whisper_model),
        ("Processamento de Áudio", test_audio_processing),
        ("Sistema de Transcrição", test_transcription_system),
        ("Detecção de Contexto", test_context_detection),
        ("Pós-processamento", test_post_processing),
        ("Transcrição Completa", test_full_transcription)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Executando: {test_name}")
        print(f"{'='*50}")
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSOU")
            else:
                print(f"❌ {test_name} FALHOU")
        except Exception as e:
            print(f"❌ {test_name} FALHOU com exceção: {e}")
    
    print(f"\n{'='*60}")
    print(f"RESULTADO FINAL: {passed}/{total} testes passaram")
    print(f"{'='*60}")
    
    if passed == total:
        print("🎉 SISTEMA FUNCIONANDO PERFEITAMENTE!")
        print("\n📋 Próximos passos:")
        print("1. Execute: python transcribe.py <arquivo_audio>")
        print("2. Configure parâmetros conforme necessário")
        print("3. Monitore logs para otimizações")
        return 0
    else:
        print("⚠️ Alguns testes falharam.")
        print("\n🔧 Soluções:")
        print("1. Execute: python install_dependencies.py")
        print("2. Verifique se FFmpeg está instalado")
        print("3. Consulte o README.md para troubleshooting")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 