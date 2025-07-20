#!/usr/bin/env python3
"""
Sistema de Pós-Processamento para Transcrições
Melhora a qualidade do texto transcrito
"""
import re
import json
import sys
from typing import List, Dict, Any
import unicodedata

class TranscriptionPostProcessor:
    def __init__(self):
        # Padrões de correção para português
        self.corrections = {
            # Correções comuns de transcrição
            r'\b(?:eu|vc|vcs|tb|pq|q|n|ñ|d|tbm|blz|vlw|obg|obrigado)\b': {
                'eu': 'eu',
                'vc': 'você',
                'vcs': 'vocês', 
                'tb': 'também',
                'pq': 'porque',
                'q': 'que',
                'n': 'não',
                'ñ': 'não',
                'd': 'de',
                'tbm': 'também',
                'blz': 'beleza',
                'vlw': 'valeu',
                'obg': 'obrigado',
                'obrigado': 'obrigado'
            },
            
            # Correções de pontuação
            r'\.{2,}': '...',  # Múltiplos pontos
            r'!{2,}': '!',     # Múltiplas exclamações
            r'\?{2,}': '?',    # Múltiplas interrogações
            r'\s+': ' ',       # Múltiplos espaços
            r'\s+([.,!?])': r'\1',  # Espaços antes de pontuação
        }
        
        # Expressões regulares para melhorias
        self.improvements = [
            # Capitalizar início de frases
            (r'^([a-z])', lambda m: m.group(1).upper()),
            (r'([.!?])\s+([a-z])', lambda m: m.group(1) + ' ' + m.group(2).upper()),
            
            # Melhorar pontuação
            (r'([a-z])\s*,\s*([a-z])', r'\1, \2'),
            (r'([a-z])\s*\.\s*([a-z])', r'\1. \2'),
            (r'([a-z])\s*!\s*([a-z])', r'\1! \2'),
            (r'([a-z])\s*\?\s*([a-z])', r'\1? \2'),
            
            # Remover espaços extras
            (r'\s+', ' '),
            (r'^\s+|\s+$', ''),  # Trim
        ]
        
        # Palavras que devem ser capitalizadas
        self.capitalize_words = {
            'brasil', 'brasileiro', 'brasileira', 'português', 'portuguesa',
            'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
            'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
            'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo',
            'deus', 'jesus', 'cristo', 'bíblia', 'igreja', 'padre', 'pastor'
        }

    def normalize_text(self, text: str) -> str:
        """Normaliza o texto (remove acentos, converte para minúsculas)"""
        # Remove acentos
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        return text.lower()

    def apply_corrections(self, text: str) -> str:
        """Aplica correções de abreviações e erros comuns"""
        for pattern, replacement in self.corrections.items():
            if isinstance(replacement, dict):
                # Substituições específicas
                for abbr, full in replacement.items():
                    text = re.sub(rf'\b{re.escape(abbr)}\b', full, text, flags=re.IGNORECASE)
            else:
                # Substituições simples
                text = re.sub(pattern, replacement, text)
        return text

    def improve_punctuation(self, text: str) -> str:
        """Melhora a pontuação e formatação"""
        for pattern, replacement in self.improvements:
            if callable(replacement):
                text = re.sub(pattern, replacement, text)
            else:
                text = re.sub(pattern, replacement, text)
        return text

    def capitalize_proper_nouns(self, text: str) -> str:
        """Capitaliza nomes próprios e palavras importantes"""
        words = text.split()
        for i, word in enumerate(words):
            # Capitalizar palavras específicas
            if word.lower() in self.capitalize_words:
                words[i] = word.capitalize()
            # Capitalizar nomes próprios (palavras que começam com maiúscula)
            elif word and word[0].isupper() and len(word) > 1:
                words[i] = word.capitalize()
        return ' '.join(words)

    def fix_common_errors(self, text: str) -> str:
        """Corrige erros comuns de transcrição"""
        fixes = [
            # Correções de palavras comuns
            (r'\b(?:ta|tá)\b', 'está'),
            (r'\b(?:to|tô)\b', 'estou'),
            (r'\b(?:tá|tao)\b', 'tão'),
            (r'\b(?:pra|pro)\b', 'para'),
            (r'\b(?:num|numa)\b', 'em um'),
            (r'\b(?:né|ne)\b', 'não é'),
            (r'\b(?:tá|ta)\b', 'está'),
            (r'\b(?:tô|to)\b', 'estou'),
            
            # Correções de pontuação
            (r'([a-z])\s*,\s*([a-z])', r'\1, \2'),
            (r'([a-z])\s*\.\s*([a-z])', r'\1. \2'),
            (r'([a-z])\s*!\s*([a-z])', r'\1! \2'),
            (r'([a-z])\s*\?\s*([a-z])', r'\1? \2'),
            
            # Remover repetições
            (r'\b(\w+)(?:\s+\1)+\b', r'\1'),
            
            # Melhorar espaçamento
            (r'\s+', ' '),
            (r'^\s+|\s+$', ''),
        ]
        
        for pattern, replacement in fixes:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text

    def improve_sentence_structure(self, text: str) -> str:
        """Melhora a estrutura das frases"""
        # Dividir em frases
        sentences = re.split(r'([.!?]+)', text)
        
        improved_sentences = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i].strip()
                punctuation = sentences[i + 1]
                
                if sentence:
                    # Capitalizar primeira letra
                    if sentence and sentence[0].islower():
                        sentence = sentence[0].upper() + sentence[1:]
                    
                    # Adicionar espaço antes da pontuação se necessário
                    if not sentence.endswith(' '):
                        sentence += ' '
                    
                    improved_sentences.append(sentence + punctuation)
            else:
                # Última frase sem pontuação
                sentence = sentences[i].strip()
                if sentence:
                    if sentence and sentence[0].islower():
                        sentence = sentence[0].upper() + sentence[1:]
                    improved_sentences.append(sentence)
        
        return ''.join(improved_sentences)

    def process_segment(self, segment: Dict[str, Any]) -> Dict[str, Any]:
        """Processa um segmento individual"""
        original_text = segment.get('text', '')
        
        if not original_text:
            return segment
        
        # Aplicar melhorias
        improved_text = original_text
        
        # 1. Aplicar correções básicas
        improved_text = self.apply_corrections(improved_text)
        
        # 2. Melhorar pontuação
        improved_text = self.improve_punctuation(improved_text)
        
        # 3. Corrigir erros comuns
        improved_text = self.fix_common_errors(improved_text)
        
        # 4. Melhorar estrutura das frases
        improved_text = self.improve_sentence_structure(improved_text)
        
        # 5. Capitalizar nomes próprios
        improved_text = self.capitalize_proper_nouns(improved_text)
        
        # Criar novo segmento com texto melhorado
        improved_segment = segment.copy()
        improved_segment['text'] = improved_text
        improved_segment['original_text'] = original_text  # Manter original
        
        return improved_segment

    def process_transcription(self, transcription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa toda a transcrição"""
        if 'segments' not in transcription_data:
            return transcription_data
        
        original_segments = transcription_data['segments']
        improved_segments = []
        
        # Processar cada segmento
        for segment in original_segments:
            improved_segment = self.process_segment(segment)
            improved_segments.append(improved_segment)
        
        # Criar resultado melhorado
        improved_data = transcription_data.copy()
        improved_data['segments'] = improved_segments
        
        # Adicionar metadados de pós-processamento
        if 'metadata' not in improved_data:
            improved_data['metadata'] = {}
        
        improved_data['metadata']['post_processed'] = True
        improved_data['metadata']['original_segments_count'] = len(original_segments)
        improved_data['metadata']['improved_segments_count'] = len(improved_segments)
        
        return improved_data

def main():
    """Função principal para processar transcrição via linha de comando"""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Uso: python post_processor.py <arquivo_transcricao.json>"}))
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    try:
        # Ler arquivo de transcrição
        with open(input_file, 'r', encoding='utf-8') as f:
            transcription_data = json.load(f)
        
        # Processar transcrição
        processor = TranscriptionPostProcessor()
        improved_data = processor.process_transcription(transcription_data)
        
        # Salvar resultado
        output_file = input_file.replace('.json', '_improved.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(improved_data, f, ensure_ascii=False, indent=2)
        
        print(json.dumps({
            "success": True,
            "input_file": input_file,
            "output_file": output_file,
            "segments_processed": len(improved_data.get('segments', [])),
            "post_processed": True
        }))
        
    except Exception as e:
        print(json.dumps({
            "error": f"Erro no pós-processamento: {str(e)}"
        }))
        sys.exit(1)

if __name__ == "__main__":
    main() 