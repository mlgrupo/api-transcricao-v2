#!/usr/bin/env python3
"""
Script para criar arquivo de áudio de teste
"""

import numpy as np
import soundfile as sf
import os

def create_test_audio():
    """Cria um arquivo de áudio de teste simples"""
    
    # Parâmetros do áudio
    sample_rate = 16000  # 16kHz
    duration = 10  # 10 segundos
    frequency = 440  # 440 Hz (nota A)
    
    # Gerar onda senoidal
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio = 0.3 * np.sin(2 * np.pi * frequency * t)
    
    # Adicionar um pouco de ruído para simular áudio real
    noise = 0.01 * np.random.normal(0, 1, len(audio))
    audio = audio + noise
    
    # Salvar arquivo
    output_file = "test_audio.wav"
    sf.write(output_file, audio, sample_rate)
    
    print(f"✅ Arquivo de teste criado: {output_file}")
    print(f"   - Duração: {duration} segundos")
    print(f"   - Sample rate: {sample_rate} Hz")
    print(f"   - Tamanho: {os.path.getsize(output_file) / 1024:.1f} KB")
    
    return output_file

if __name__ == "__main__":
    create_test_audio() 