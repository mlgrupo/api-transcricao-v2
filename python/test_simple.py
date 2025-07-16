#!/usr/bin/env python3
"""
Teste simples da transcrição
"""

import sys
import os
from pathlib import Path

def test_transcription():
    """Testa a transcrição com um arquivo de exemplo"""
    
    # Verificar se o script existe
    script_path = Path("transcribe.py")
    if not script_path.exists():
        print("❌ Script transcribe.py não encontrado")
        return False
    
    # Criar um arquivo de áudio de teste simples
    test_audio_path = "test_audio.wav"
    
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        
        # Criar 3 segundos de tom de teste
        tone = Sine(440).to_audio_segment(duration=3000)
        tone.export(test_audio_path, format="wav")
        
        print(f"✅ Arquivo de teste criado: {test_audio_path}")
        
        # Executar transcrição
        import subprocess
        result = subprocess.run([
            sys.executable, "transcribe.py", test_audio_path
        ], capture_output=True, text=True, timeout=60)
        
        print(f"📤 stdout: {result.stdout}")
        if result.stderr:
            print(f"📤 stderr: {result.stderr}")
        
        # Verificar se retornou JSON válido
        try:
            import json
            output = json.loads(result.stdout.strip())
            if output.get("status") == "success" and output.get("text"):
                print("✅ Transcrição funcionando corretamente!")
                print(f"📝 Texto: {output['text']}")
                return True
            else:
                print("❌ Transcrição falhou")
                return False
        except json.JSONDecodeError:
            print("❌ Resultado não é JSON válido")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False
    finally:
        # Limpar arquivo de teste
        if os.path.exists(test_audio_path):
            os.remove(test_audio_path)

if __name__ == "__main__":
    print("🧪 Teste Simples da Transcrição")
    print("=" * 40)
    
    success = test_transcription()
    
    if success:
        print("\n🎉 Teste passou! Sistema funcionando.")
        sys.exit(0)
    else:
        print("\n💥 Teste falhou! Verifique o sistema.")
        sys.exit(1) 