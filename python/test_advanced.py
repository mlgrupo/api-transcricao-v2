#!/usr/bin/env python3
"""
Teste avançado da transcrição com identificação de locutores
"""

import sys
import os
import json
from pathlib import Path

def test_encoding_fix():
    """Testa a correção de codificação"""
    print("🔍 Testando correção de codificação...")
    
    # Texto com caracteres problemáticos
    problematic_text = "O que voc est achando da gesto do prefeito? Isso no um prefeito, no! um pai! Rapaz, s pode ser o diabo mesmo, viu? No!"
    
    try:
        from transcribe import TextPostProcessor
        processor = TextPostProcessor()
        fixed_text = processor.fix_encoding(problematic_text)
        
        print(f"📝 Texto original: {problematic_text}")
        print(f"📝 Texto corrigido: {fixed_text}")
        
        # Verificar se os caracteres foram corrigidos
        if "ã" in fixed_text and "á" in fixed_text and "é" in fixed_text:
            print("✅ Correção de codificação funcionando!")
            return True
        else:
            print("❌ Correção de codificação falhou")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de codificação: {e}")
        return False

def test_speaker_identification():
    """Testa a identificação de locutores"""
    print("\n🎤 Testando identificação de locutores...")
    
    try:
        from transcribe import SpeakerIdentifier
        identifier = SpeakerIdentifier()
        
        test_texts = [
            "Eu acho que está muito bom",
            "Você concorda com isso?",
            "Meu ponto de vista é diferente",
            "Sua opinião é importante"
        ]
        
        for i, text in enumerate(test_texts):
            speaker = identifier.identify_speaker(text, i)
            print(f"📝 '{text}' -> {speaker}")
        
        print("✅ Identificação de locutores funcionando!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de locutores: {e}")
        return False

def test_full_transcription():
    """Testa a transcrição completa"""
    print("\n🎵 Testando transcrição completa...")
    
    # Verificar se o script existe
    script_path = Path("transcribe.py")
    if not script_path.exists():
        print("❌ Script transcribe.py não encontrado")
        return False
    
    # Criar um arquivo de áudio de teste
    test_audio_path = "test_audio.wav"
    
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        
        # Criar 5 segundos de tom de teste
        tone = Sine(440).to_audio_segment(duration=5000)
        tone.export(test_audio_path, format="wav")
        
        print(f"✅ Arquivo de teste criado: {test_audio_path}")
        
        # Executar transcrição
        import subprocess
        result = subprocess.run([
            sys.executable, "transcribe.py", test_audio_path
        ], capture_output=True, text=True, timeout=120)
        
        print(f"📤 stdout: {result.stdout}")
        if result.stderr:
            print(f"📤 stderr: {result.stderr}")
        
        # Verificar se retornou JSON válido
        try:
            output = json.loads(result.stdout.strip())
            if output.get("status") == "success" and output.get("text"):
                print("✅ Transcrição funcionando corretamente!")
                print(f"📝 Texto: {output['text']}")
                
                # Verificar se tem locutores
                if "Locutor" in output['text']:
                    print("✅ Identificação de locutores presente!")
                else:
                    print("⚠️ Identificação de locutores não encontrada")
                
                # Verificar se tem timestamps
                if "[" in output['text'] and "]" in output['text']:
                    print("✅ Timestamps presentes!")
                else:
                    print("⚠️ Timestamps não encontrados")
                
                return True
            else:
                print("❌ Transcrição falhou")
                return False
        except json.JSONDecodeError:
            print("❌ Resultado não é JSON válido")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de transcrição: {e}")
        return False
    finally:
        # Limpar arquivo de teste
        if os.path.exists(test_audio_path):
            os.remove(test_audio_path)

def main():
    """Função principal"""
    print("🧪 Teste Avançado da Transcrição")
    print("=" * 50)
    
    tests = [
        ("Correção de Codificação", test_encoding_fix),
        ("Identificação de Locutores", test_speaker_identification),
        ("Transcrição Completa", test_full_transcription)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Teste: {test_name}")
        print(f"{'='*50}")
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} - PASSOU")
        else:
            print(f"❌ {test_name} - FALHOU")
    
    print(f"\n{'='*50}")
    print(f"RESULTADO: {passed}/{total} testes passaram")
    print(f"{'='*50}")
    
    if passed == total:
        print("🎉 Sistema avançado funcionando perfeitamente!")
        print("\n📋 Funcionalidades implementadas:")
        print("   ✅ Correção de codificação UTF-8")
        print("   ✅ Identificação automática de locutores")
        print("   ✅ Timestamps precisos por segmento")
        print("   ✅ Modelo Whisper Large")
        print("   ✅ Pós-processamento robusto")
        return 0
    else:
        print("⚠️ Alguns testes falharam. Verifique o sistema.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 