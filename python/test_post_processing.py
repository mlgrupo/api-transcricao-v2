#!/usr/bin/env python3
"""
Teste do Sistema de Pós-Processamento
Demonstra as melhorias aplicadas na transcrição
"""
import json
from post_processor import TranscriptionPostProcessor

def test_post_processing():
    """Testa o pós-processamento com exemplos reais"""
    
    # Exemplo de transcrição com erros comuns
    sample_transcription = {
        "segments": [
            {
                "start": 0.0,
                "end": 5.2,
                "text": "oi pessoal, blz? eu tô aqui pra falar sobre o brasil e como vc pode ajudar tb"
            },
            {
                "start": 5.2,
                "end": 10.5,
                "text": "vc sabe né? a gente precisa fazer algo pq ta muito ruim"
            },
            {
                "start": 10.5,
                "end": 15.8,
                "text": "eu tô falando sério... vcs precisam entender q isso é importante"
            },
            {
                "start": 15.8,
                "end": 20.1,
                "text": "obg por assistir! vlw pessoal, até mais"
            }
        ],
        "metadata": {
            "language": "pt",
            "model_used": "medium"
        }
    }
    
    print("🧪 Teste do Sistema de Pós-Processamento")
    print("=" * 50)
    
    # Processar transcrição
    processor = TranscriptionPostProcessor()
    improved_data = processor.process_transcription(sample_transcription)
    
    print("\n📝 ANTES (Transcrição Original):")
    print("-" * 30)
    for i, segment in enumerate(sample_transcription["segments"]):
        print(f"Segmento {i+1}: {segment['text']}")
    
    print("\n✨ DEPOIS (Pós-Processamento):")
    print("-" * 30)
    for i, segment in enumerate(improved_data["segments"]):
        print(f"Segmento {i+1}: {segment['text']}")
    
    print("\n🔧 Melhorias Aplicadas:")
    print("-" * 30)
    improvements = improved_data["metadata"].get("improvements_applied", [])
    for improvement in improvements:
        print(f"✅ {improvement}")
    
    print("\n📊 Estatísticas:")
    print("-" * 30)
    print(f"Segmentos processados: {len(improved_data['segments'])}")
    print(f"Pós-processamento: {improved_data['metadata'].get('post_processed', False)}")
    
    # Salvar exemplo
    with open("exemplo_pos_processamento.json", "w", encoding="utf-8") as f:
        json.dump(improved_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Exemplo salvo em: exemplo_pos_processamento.json")

def test_individual_corrections():
    """Testa correções individuais"""
    
    processor = TranscriptionPostProcessor()
    
    test_cases = [
        ("oi vc ta blz?", "Oi você está beleza?"),
        ("eu tô aqui no brasil", "Eu estou aqui no Brasil"),
        ("vc sabe né? ta muito ruim", "Você sabe não é? Está muito ruim"),
        ("obg por tudo! vlw", "Obrigado por tudo! Valeu"),
        ("eu tbm quero ajudar", "Eu também quero ajudar"),
        ("pq vc não vem?", "Porque você não vem?"),
    ]
    
    print("\n🔍 Teste de Correções Individuais:")
    print("-" * 40)
    
    for original, expected in test_cases:
        corrected = processor.apply_corrections(original)
        corrected = processor.improve_punctuation(corrected)
        corrected = processor.fix_common_errors(corrected)
        corrected = processor.improve_sentence_structure(corrected)
        corrected = processor.capitalize_proper_nouns(corrected)
        
        print(f"Original: {original}")
        print(f"Corrigido: {corrected}")
        print(f"Esperado: {expected}")
        print("-" * 20)

if __name__ == "__main__":
    test_post_processing()
    test_individual_corrections() 