import re
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class TextProcessingRules:
    """Regras configuráveis para processamento de texto"""
    capitalize_sentences: bool = True
    fix_spaces: bool = True
    ensure_final_punctuation: bool = True
    normalize_numbers: bool = True
    fix_common_errors: bool = True
    normalize_punctuation: bool = True

    # Pontuação que deve ter espaço depois
    punctuation_with_space_after: List[str] = field(default_factory=lambda: ['.', ',', '!', '?', ':', ';'])
    # Pontuação que não deve ter espaço antes
    punctuation_no_space_before: List[str] = field(default_factory=lambda: ['.', ',', '!', '?', ':', ';', ')'])
    # Pontuação que não deve ter espaço depois
    punctuation_no_space_after: List[str] = field(default_factory=lambda: ['('])
    # Substituições comuns (erros frequentes)
    common_replacements: Dict[str, str] = field(default_factory=lambda: {
        'né': 'não é',
        'tá': 'está',
        'pra': 'para',
        'pro': 'para o',
        'num': 'não',
        'nao': 'não',
        'entao': 'então',
        'tbm': 'também',
        'hj': 'hoje',
        'pq': 'porque',
        'mto': 'muito',
        '100%': 'cem por cento',
        '1%': 'um por cento',
        'oakunta': 'pergunta'     
    })
    # Palavras que devem ser capitalizadas
    capitalize_words: List[str] = field(default_factory=lambda: [
        'Brasil',
        'São Paulo',
        'Rio de Janeiro',
        'Janeiro',
        'Fevereiro',
        'Março',
        'Abril',
        'Maio',
        'Junho',
        'Julho',
        'Agosto',
        'Setembro',
        'Outubro',
        'Novembro',
        'Dezembro'
    ])

class TextProcessor:
    def __init__(self, rules: Optional[TextProcessingRules] = None):
        self.rules = rules or TextProcessingRules()
        self.setup_regex_patterns()

    def setup_regex_patterns(self):
        """Compila expressões regulares para melhor performance"""
        # Padrão para encontrar números
        self.number_pattern = re.compile(r'\d+')
        # Padrão para múltiplos espaços
        self.multiple_spaces = re.compile(r'\s+')
        # Padrão para espaços antes de pontuação
        punct_before = ''.join(self.rules.punctuation_no_space_before)
        self.space_before_punct = re.compile(f'\\s+([{re.escape(punct_before)}])')
        # Padrão para espaços depois de pontuação
        punct_after = ''.join(self.rules.punctuation_with_space_after)
        self.space_after_punct = re.compile(f'([{re.escape(punct_after)}])(?!\\s)')
        # Padrão para encontrar sentenças
        self.sentence_pattern = re.compile(r'([.!?]\s+)([a-z])')

    def normalize_numbers(self, text: str) -> str:
        """Normaliza números no texto"""
        def replace_number(match):
            num = int(match.group(0))
            if num <= 10:  # Números até 10 são escritos por extenso
                numbers = ['zero', 'um', 'dois', 'três', 'quatro', 'cinco', 
                          'seis', 'sete', 'oito', 'nove', 'dez']
                return numbers[num]
            return match.group(0)
        
        return self.number_pattern.sub(replace_number, text)

    def fix_spaces(self, text: str) -> str:
        """Corrige espaçamento"""
        # Remove múltiplos espaços
        text = self.multiple_spaces.sub(' ', text)
        # Remove espaços antes de pontuação
        text = self.space_before_punct.sub(r'\1', text)
        # Adiciona espaço depois de pontuação
        text = self.space_after_punct.sub(r'\1 ', text)
        return text.strip()

    def capitalize_sentences(self, text: str) -> str:
        """Capitaliza início de sentenças"""
        # Capitaliza primeira letra do texto
        if text:
            text = text[0].upper() + text[1:]
        # Capitaliza após pontuação final
        text = self.sentence_pattern.sub(lambda m: m.group(1) + m.group(2).upper(), text)
        # Capitaliza palavras específicas
        for word in self.rules.capitalize_words:
            pattern = re.compile(rf'\b{word.lower()}\b', re.IGNORECASE)
            text = pattern.sub(word, text)
        return text

    def fix_common_errors(self, text: str) -> str:
        """Corrige erros comuns e abreviações"""
        words = text.split()
        for i, word in enumerate(words):
            lower_word = word.lower()
            if lower_word in self.rules.common_replacements:
                words[i] = self.rules.common_replacements[lower_word]
        return ' '.join(words)
    
    def ensure_final_punctuation(self, text: str) -> str:
        """Garante que o texto termina com pontuação adequada"""
        text = text.rstrip()
        if text and not text[-1] in '.!?':
            text += '.'
        return text

    def remove_redundancies(self, text: str) -> str:
        """Remove redundâncias e repetições no texto."""
        sentences = text.split('.')
        unique_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and sentence not in unique_sentences:
                unique_sentences.append(sentence)
        return '. '.join(unique_sentences).strip()

    def process(self, text: str) -> str:
        """Processa o texto aplicando todas as regras configuradas"""
        try:
            if self.rules.fix_common_errors:
                text = self.fix_common_errors(text)
            if self.rules.normalize_numbers:
                text = self.normalize_numbers(text)
            if self.rules.fix_spaces:
                text = self.fix_spaces(text)
            if self.rules.capitalize_sentences:
                text = self.capitalize_sentences(text)
            if self.rules.ensure_final_punctuation:
                text = self.ensure_final_punctuation(text)
            # Adicionar remoção de redundâncias
            text = self.remove_redundancies(text)
            logger.info("Texto processado com sucesso")
            return text
        except Exception as e:
            logger.error(f"Erro no processamento do texto: {str(e)}")
            return text  # Retorna texto original em caso de erro

    @classmethod
    def from_json(cls, json_path: str) -> 'TextProcessor':
        """Cria um processador com regras carregadas de um arquivo JSON"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                rules_dict = json.load(f)
            rules = TextProcessingRules(**rules_dict)
            return cls(rules)
        except Exception as e:
            logger.error(f"Erro ao carregar regras do JSON: {str(e)}")
            return cls()
