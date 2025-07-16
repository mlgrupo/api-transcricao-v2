# 🎤 Sistema Avançado de Transcrição

Sistema de transcrição de áudio/vídeo com processamento paralelo, gestão inteligente de memória e melhorias de qualidade.

## ✨ Características Principais

### 🚀 **Processamento Paralelo**
- Transcreve chunks em paralelo usando multiprocessing
- Pipeline assíncrono: enquanto transcreve chunk N, já prepara chunk N+1
- ThreadPoolExecutor para operações I/O (salvar/carregar arquivos)

### 💾 **Gestão de Memória**
- Limita número máximo de chunks na memória simultaneamente
- Streaming de resultados (retorna chunks conforme ficam prontos)
- Garbage collection forçado após cada chunk processado

### 🎵 **Pré-processamento de Áudio**
- Normalização automática de volume
- Redução de ruído usando noisereduce
- Detecção e remoção de silêncios longos com webrtcvad
- Conversão automática para formato ideal (16kHz mono)

### 🧠 **Prompt Engineering Avançado**
- Prompts específicos por tipo de conteúdo:
  - **Reunião**: Estrutura formal de ata, decisões, prazos
  - **Entrevista**: Perguntas/respostas, citações, contexto emocional
  - **Palestra**: Conceitos, exemplos, estrutura didática
  - **Podcast**: Tom conversacional, opiniões, interações
- Detecção automática de contexto baseada no nome do arquivo

### ✨ **Pós-processamento Inteligente**
- Correção ortográfica usando spellchecker brasileiro
- Detecção e correção de nomes próprios/marcas
- Formatação automática de números, datas, horários
- Detecção de emoções/tons na fala (opcional)

## 📋 Requisitos

- Python 3.8+
- FFmpeg instalado e no PATH
- Mínimo 8GB RAM (recomendado 16GB+)
- CPU multi-core (recomendado 4+ cores)

## 🚀 Instalação

### 1. Instalação Automática (Recomendado)

```bash
cd python
python install_dependencies.py
```

### 2. Instalação Manual

```bash
# Instalar dependências Python
pip install -r requirements.txt

# Instalar PyTorch (CPU)
pip install torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu

# Instalar spaCy e modelo português
pip install spacy==3.7.2
python -m spacy download pt_core_news_sm

# Instalar FFmpeg (Windows)
# Baixe de: https://ffmpeg.org/download.html
# Adicione ao PATH do sistema
```

### 3. Verificar Instalação

```bash
python test_system.py
```

## 🎯 Uso

### Transcrição Básica

```bash
python transcribe.py "caminho/para/audio.mp3"
```

### Transcrição com Diretório de Saída

```bash
python transcribe.py "caminho/para/audio.mp3" "diretorio/saida"
```

### Configuração Avançada

```python
from transcribe import TranscriptionConfig, ParallelTranscriptionProcessor

# Configuração personalizada
config = TranscriptionConfig(
    chunk_duration_ms=3 * 60 * 1000,  # 3 minutos por chunk
    max_workers=6,                     # 6 workers paralelos
    max_memory_chunks=5,              # Máximo 5 chunks na memória
    enableNoiseReduction=True,
    enableSilenceRemoval=True,
    enableEmotionDetection=True
)

# Processador
processor = ParallelTranscriptionProcessor(config)

# Transcrever
result = processor.transcribe("audio.mp3")
```

## ⚙️ Configuração

### Variáveis de Ambiente

```bash
# Configurações de processamento
TRANSCRIPTION_MAX_WORKERS=4
TRANSCRIPTION_CHUNK_DURATION=300000  # 5 minutos em ms
TRANSCRIPTION_MAX_MEMORY_CHUNKS=3

# Configurações de qualidade
ENABLE_NOISE_REDUCTION=true
ENABLE_SILENCE_REMOVAL=true
ENABLE_VOLUME_NORMALIZATION=true
ENABLE_CONTEXT_DETECTION=true
ENABLE_SPELL_CHECK=true
ENABLE_EMOTION_DETECTION=false
```

### Configuração via Código

```python
# Atualizar configuração em tempo real
processor.updateConfig({
    'maxWorkers': 8,
    'enableEmotionDetection': True,
    'chunkDurationMs': 2 * 60 * 1000  # 2 minutos
})
```

## 📊 Monitoramento

### Status do Sistema

```python
# Verificar status do sistema
status = await processor.checkSystemStatus()
print(f"Python: {status.pythonAvailable}")
print(f"Whisper: {status.whisperAvailable}")
print(f"Dependências: {status.dependenciesAvailable}")
print(f"Memória: {status.memoryUsage}MB")
print(f"CPU Cores: {status.cpuCores}")
```

### Logs Detalhados

O sistema gera logs detalhados incluindo:
- Progresso de cada chunk
- Métricas de performance
- Detecção de contexto
- Emoções detectadas
- Uso de memória

## 🔧 Troubleshooting

### Erro: "FFmpeg não encontrado"
```bash
# Windows
# Baixe FFmpeg de https://ffmpeg.org/download.html
# Adicione ao PATH do sistema

# Linux
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

### Erro: "CUDA out of memory"
```python
# Reduzir número de workers
config.max_workers = 2
config.max_memory_chunks = 1
```

### Erro: "Modelo Whisper não encontrado"
```bash
# Baixar modelo manualmente
python -c "import whisper; whisper.load_model('large')"
```

### Performance Lenta
```python
# Usar modelo menor
model = whisper.load_model("medium")  # ou "small", "base"

# Aumentar workers (se CPU suportar)
config.max_workers = 8
```

## 📈 Performance

### Benchmarks Típicos

| Configuração | Tempo (min/10min áudio) | Memória | Qualidade |
|--------------|-------------------------|---------|-----------|
| CPU 4 cores | 8-12 min | 4-6GB | Excelente |
| CPU 8 cores | 4-6 min | 6-8GB | Excelente |
| GPU RTX 3080 | 2-3 min | 8-12GB | Excelente |

### Otimizações

1. **Para CPU limitado**: Reduzir `max_workers` e `chunk_duration_ms`
2. **Para memória limitada**: Reduzir `max_memory_chunks`
3. **Para velocidade**: Usar modelo "medium" em vez de "large"
4. **Para qualidade**: Manter modelo "large" e aumentar `chunk_duration_ms`

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para detalhes.

## 🆘 Suporte

Para suporte técnico:
- Abra uma issue no GitHub
- Consulte a documentação
- Verifique os logs de erro

---

**Desenvolvido com ❤️ para transcrições de alta qualidade** 