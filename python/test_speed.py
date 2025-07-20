#!/usr/bin/env python3
"""
Script de teste para comparar velocidade dos modelos Whisper
"""

import time
import whisper
import torch

def test_model_speed(model_name: str, test_audio_path: str = "test_audio.wav"):
    """Testa a velocidade de um modelo Whisper"""
    print(f"\n🧪 Testando modelo: {model_name}")
    
    # Carregar modelo
    start_time = time.time()
    model = whisper.load_model(model_name, device="cpu")
    load_time = time.time() - start_time
    print(f"⏱️  Tempo de carregamento: {load_time:.2f}s")
    
    # Configurar PyTorch para máxima performance
    torch.set_num_threads(8)
    torch.set_default_dtype(torch.float32)
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.deterministic = False
    torch.set_grad_enabled(False)
    
    # Teste de transcrição (se arquivo existir)
    try:
        start_time = time.time()
        result = model.transcribe(
            test_audio_path,
            beam_size=2,
            best_of=1,
            temperature=0.0,
            patience=1,
            length_penalty=1.0,
            word_timestamps=True,
            condition_on_previous_text=False,
            language="pt"
        )
        transcribe_time = time.time() - start_time
        print(f"⚡ Tempo de transcrição: {transcribe_time:.2f}s")
        print(f"📝 Texto gerado: {result['text'][:100]}...")
        return transcribe_time
    except FileNotFoundError:
        print(f"⚠️  Arquivo {test_audio_path} não encontrado, pulando teste de transcrição")
        return None

def main():
    print("🚀 Teste de Velocidade - Modelos Whisper")
    print("=" * 50)
    
    # Testar modelos
    models = ["tiny", "base", "small", "medium"]
    results = {}
    
    for model in models:
        transcribe_time = test_model_speed(model)
        if transcribe_time:
            results[model] = transcribe_time
    
    # Comparação
    if results:
        print("\n📊 Comparação de Velocidade:")
        print("-" * 30)
        
        fastest_model = min(results, key=results.get)
        fastest_time = results[fastest_model]
        
        for model, time_taken in results.items():
            speed_factor = fastest_time / time_taken
            print(f"{model:6} | {time_taken:6.2f}s | {speed_factor:5.1f}x {'🚀' if model == fastest_model else ''}")
        
        print(f"\n🎯 Recomendação: Use o modelo '{fastest_model}' para máxima velocidade!")

if __name__ == "__main__":
    main() 