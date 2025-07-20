# 🏗️ Arquitetura Robusta de Diarização

Sistema completo de transcrição e diarização otimizado para processamento de múltiplos vídeos simultâneos com gestão inteligente de recursos.

## 📋 Visão Geral

Esta arquitetura foi projetada para processar **2 vídeos de 2 horas simultâneos** em um servidor com **8 vCPUs e 32GB RAM**, garantindo robustez, eficiência e qualidade profissional.

### 🎯 Características Principais

- ✅ **Processamento Paralelo**: Até 2 vídeos simultâneos
- ✅ **Gestão Inteligente de Recursos**: Controle automático de RAM/CPU
- ✅ **Recovery Automático**: Recuperação de falhas sem interrupção
- ✅ **Qualidade Profissional**: Whisper Large + PyAnnote para máxima precisão
- ✅ **Monitoramento em Tempo Real**: Logs estruturados e métricas
- ✅ **API Simples**: Interface fácil de usar

## 🏛️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    DIARIZATION ORCHESTRATOR                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   RESOURCE  │  │   AUDIO     │  │   WHISPER   │         │
│  │  MANAGER    │  │  CHUNKER    │  │ PROCESSOR   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  SPEAKER    │  │TRANSCRIPTION│  │   QUEUE     │         │
│  │ DIARIZER    │  │   MERGER    │  │  MANAGER    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 🔧 Componentes

1. **ResourceManager** - Gestão inteligente de recursos
2. **AudioChunker** - Divisão inteligente em chunks
3. **WhisperProcessor** - Transcrição otimizada
4. **SpeakerDiarizer** - Identificação de speakers
5. **TranscriptionMerger** - Combinação de resultados
6. **DiarizationOrchestrator** - Orquestrador principal

## 🚀 Instalação

### 1. Setup Inicial

```bash
# Executar setup robusto
python setup_robust.py
```

### 2. Verificar Instalação

```bash
# Executar testes de validação
python test_robust_architecture.py
```

### 3. Configuração (Opcional)

```bash
# Configurar token do HuggingFace (se necessário)
export HF_TOKEN="seu_token_aqui"
```

## 📖 Uso Básico

### Processamento Simples

```python
from diarization_orchestrator import DiarizationOrchestrator, OrchestratorConfig

# Configurar orquestrador
config = OrchestratorConfig(
    max_concurrent_jobs=2,
    chunk_duration=30.0,
    chunk_overlap=5.0,
    whisper_model="large-v3"
)

# Processar arquivo
with DiarizationOrchestrator(config) as orchestrator:
    job_id = orchestrator.process_file(
        "caminho/para/video.mp4",
        "caminho/para/saida"
    )
    
    # Aguardar conclusão
    while True:
        status = orchestrator.get_job_status(job_id)
        if status["status"] in ["completed", "failed"]:
            break
        time.sleep(5)
```

### Processamento Concorrente

```python
# Submeter múltiplos arquivos
audio_files = ["video1.mp4", "video2.mp4", "video3.mp4"]
job_ids = []

for audio_file in audio_files:
    job_id = orchestrator.process_file(audio_file, f"output_{job_id}")
    job_ids.append(job_id)

# Monitorar todos os jobs
for job_id in job_ids:
    status = orchestrator.get_job_status(job_id)
    print(f"Job {job_id}: {status['status']}")
```

### Processamento com Prioridades

```python
from resource_manager import JobPriority

# Jobs com diferentes prioridades
orchestrator.submit_job("urgente.mp4", "output_urgente", JobPriority.HIGH)
orchestrator.submit_job("normal.mp4", "output_normal", JobPriority.NORMAL)
orchestrator.submit_job("baixa.mp4", "output_baixa", JobPriority.LOW)
```

## ⚙️ Configuração Avançada

### OrchestratorConfig

```python
config = OrchestratorConfig(
    max_concurrent_jobs=2,      # Jobs simultâneos
    max_memory_gb=28.0,         # Limite de memória
    chunk_duration=30.0,        # Duração do chunk (segundos)
    chunk_overlap=5.0,          # Overlap entre chunks
    whisper_model="large-v3",   # Modelo Whisper
    max_speakers=8,             # Máximo de speakers
    enable_recovery=True,       # Recovery automático
    enable_monitoring=True,     # Monitoramento
    log_interval=30             # Intervalo de log (segundos)
)
```

### Configurações por Componente

#### ResourceManager
```python
from resource_manager import ResourceManager

rm = ResourceManager("config.json")  # Arquivo de configuração personalizado
```

#### AudioChunker
```python
from audio_chunker import ChunkingConfig, AudioChunker

config = ChunkingConfig(
    chunk_duration=30.0,
    overlap_duration=5.0,
    min_silence_duration=0.5,
    silence_threshold=-40.0,
    vad_aggressiveness=2
)
chunker = AudioChunker(config)
```

#### WhisperProcessor
```python
from whisper_processor import WhisperConfig, WhisperProcessor

config = WhisperConfig(
    model_name="large-v3",
    temperature=0.0,
    batch_size=4,
    max_retries=3,
    device="cpu"
)
processor = WhisperProcessor(config)
```

#### SpeakerDiarizer
```python
from speaker_diarizer import DiarizationConfig, SpeakerDiarizer

config = DiarizationConfig(
    max_speakers=8,
    min_speaker_duration=1.0,
    confidence_threshold=0.5,
    device="cpu"
)
diarizer = SpeakerDiarizer(config)
```

## 📊 Monitoramento e Métricas

### Status do Sistema

```python
# Obter status completo
status = orchestrator.get_system_status()

print(f"Jobs ativos: {status['active_jobs']}")
print(f"Jobs completados: {status['completed_jobs']}")
print(f"Memória usada: {status['resource_manager']['memory']['used_gb']:.2f}GB")
print(f"CPU: {status['resource_manager']['cpu']['percent']:.1f}%")
```

### Logs Estruturados

```python
import structlog

logger = structlog.get_logger()
logger.info("Processamento iniciado", 
           job_id=job_id, 
           file_path=file_path,
           estimated_duration="2h")
```

### Métricas de Performance

```python
# Estatísticas do orquestrador
stats = orchestrator.get_system_status()["orchestrator_stats"]
print(f"Tempo médio: {stats['average_processing_time']:.2f}s")
print(f"Pico de memória: {stats['peak_memory_usage']:.2f}GB")
print(f"Taxa de sucesso: {stats['successful_jobs']/stats['total_jobs_processed']*100:.1f}%")
```

## 🔧 Troubleshooting

### Problemas Comuns

#### 1. Erro de Memória
```
❌ Erro: CUDA out of memory
```
**Solução**: Reduzir `max_concurrent_jobs` ou `max_memory_gb`

#### 2. Falha na Diarização
```
❌ Erro: pyannote.audio not found
```
**Solução**: Executar `python setup_robust.py` novamente

#### 3. Processamento Lento
```
⚠️ Processamento muito lento
```
**Soluções**:
- Usar modelo Whisper menor (`base` em vez de `large-v3`)
- Aumentar `chunk_duration`
- Reduzir `chunk_overlap`

### Logs de Debug

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Ou configurar structlog para debug
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

## 📈 Performance

### Benchmarks Típicos

| Configuração | Tempo por Hora | Memória | CPU |
|--------------|----------------|---------|-----|
| 1 vídeo, Whisper Large | ~45 min | ~12GB | ~80% |
| 2 vídeos, Whisper Large | ~90 min | ~24GB | ~90% |
| 1 vídeo, Whisper Base | ~20 min | ~8GB | ~60% |

### Otimizações

#### Para Máxima Velocidade
```python
config = OrchestratorConfig(
    max_concurrent_jobs=4,
    chunk_duration=60.0,  # Chunks maiores
    chunk_overlap=2.0,    # Menos overlap
    whisper_model="base"  # Modelo menor
)
```

#### Para Máxima Qualidade
```python
config = OrchestratorConfig(
    max_concurrent_jobs=1,
    chunk_duration=15.0,  # Chunks menores
    chunk_overlap=8.0,    # Mais overlap
    whisper_model="large-v3"  # Modelo maior
)
```

## 🧪 Testes

### Executar Todos os Testes

```bash
python test_robust_architecture.py
```

### Testes Específicos

```bash
# Teste de componentes individuais
python -m pytest test_robust_architecture.py::TestRobustArchitecture::test_resource_manager

# Teste de performance
python -m pytest test_robust_architecture.py::TestRobustArchitecture::test_performance_benchmark

# Teste de concorrência
python -m pytest test_robust_architecture.py::TestRobustArchitecture::test_concurrent_processing
```

## 📁 Estrutura de Saída

```
output_directory/
├── chunks/                    # Chunks de áudio
│   ├── chunk_0000.wav
│   ├── chunk_0001.wav
│   └── chunks_metadata.json
├── whisper_results.json       # Resultados Whisper
├── diarization_results.json   # Resultados diarização
├── final_transcription.json   # Transcrição final
└── transcription.srt         # Arquivo SRT
```

### Formato da Transcrição Final

```json
{
  "file_path": "video.mp4",
  "total_duration": 7200.0,
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "segments": [
    {
      "speaker_id": "SPEAKER_00",
      "start_time": 0.0,
      "end_time": 5.2,
      "text": "Olá, como você está?",
      "confidence": 0.95
    }
  ]
}
```

## 🔄 Integração com APIs

### API REST Simples

```python
from flask import Flask, request, jsonify
from diarization_orchestrator import DiarizationOrchestrator

app = Flask(__name__)
orchestrator = DiarizationOrchestrator()

@app.route('/process', methods=['POST'])
def process_video():
    data = request.json
    file_path = data['file_path']
    output_dir = data['output_dir']
    
    job_id = orchestrator.process_file(file_path, output_dir)
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def get_status(job_id):
    status = orchestrator.get_job_status(job_id)
    return jsonify(status)

if __name__ == '__main__':
    app.run(debug=True)
```

### Webhook para Notificações

```python
def job_completed_callback(job):
    # Enviar notificação
    import requests
    requests.post('https://api.exemplo.com/webhook', json={
        'job_id': job.job_id,
        'status': job.status,
        'completed_at': job.completed_at
    })

orchestrator.add_job_completion_callback(job_completed_callback)
```

## 🛡️ Segurança e Boas Práticas

### Gestão de Recursos

- ✅ Limite automático de memória (28GB)
- ✅ Timeout por chunk (10 minutos)
- ✅ Retry automático (3 tentativas)
- ✅ Cleanup de recursos

### Tratamento de Erros

- ✅ Recovery automático
- ✅ Logs estruturados
- ✅ Graceful shutdown
- ✅ Validação de entrada

### Monitoramento

- ✅ Métricas em tempo real
- ✅ Alertas de memória
- ✅ Logs de performance
- ✅ Estatísticas de uso

## 📞 Suporte

### Logs de Diagnóstico

```bash
# Verificar logs do sistema
tail -f logs/orchestrator.log

# Verificar uso de recursos
python -c "import psutil; print(f'RAM: {psutil.virtual_memory().percent}%')"
```

### Comandos Úteis

```bash
# Verificar instalação
python -c "import whisper, pyannote.audio; print('OK')"

# Teste rápido
python example_robust_usage.py

# Benchmark
python test_robust_architecture.py
```

## 🎯 Roadmap

- [ ] Suporte a GPU (CUDA)
- [ ] API REST completa
- [ ] Dashboard web
- [ ] Integração com cloud storage
- [ ] Suporte a mais idiomas
- [ ] Modelos customizados

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para detalhes.

## 🤝 Contribuição

Contribuições são bem-vindas! Por favor, leia o CONTRIBUTING.md antes de submeter pull requests.

---

**Desenvolvido com ❤️ para processamento robusto de diarização** 