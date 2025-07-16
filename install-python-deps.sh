#!/bin/bash
set -e

# Instala dependências principais
pip install -r python/requirements.txt
# Instala dependências de diarização avançada
pip install -r python/requirements-diarization.txt

echo "Dependências Python instaladas com sucesso!" 