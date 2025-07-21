#!/bin/bash

echo "🐍 Instalando dependências Python otimizadas..."

# Verificar se o Python está instalado
echo "📁 Verificando Python..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Erro: Python3 não encontrado"
    exit 1
fi

# Verificar se pip está instalado
echo "📦 Verificando pip..."
pip3 --version
if [ $? -ne 0 ]; then
    echo "❌ Erro: pip3 não encontrado"
    exit 1
fi

# Atualizar pip
echo "🔄 Atualizando pip..."
pip3 install --upgrade pip

# Instalar dependências
echo "📥 Instalando dependências..."
cd python

# Instalar NumPy primeiro (base)
echo "🔧 Instalando NumPy..."
pip3 install "numpy>=1.21.0,<2.0.0"

# Instalar PyTorch (CPU otimizado)
echo "🔥 Instalando PyTorch..."
pip3 install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Instalar Whisper
echo "🎤 Instalando Whisper..."
pip3 install openai-whisper==20231117

# Instalar outras dependências
echo "📚 Instalando outras dependências..."
pip3 install pydub==0.25.1
pip3 install ffmpeg-python>=0.2.0
pip3 install tqdm>=4.64.0
pip3 install tiktoken>=0.4.0
pip3 install numba>=0.56.0
pip3 install more-itertools>=8.14.0
pip3 install colorama>=0.4.5

# Verificar instalação
echo "✅ Verificando instalação..."
python3 -c "
import numpy as np
import torch
import whisper
import pydub
print('✅ NumPy:', np.__version__)
print('✅ PyTorch:', torch.__version__)
print('✅ Whisper instalado com sucesso')
print('✅ Pydub instalado com sucesso')
print('✅ Todas as dependências instaladas!')
"

echo ""
echo "🎯 Instalação concluída com sucesso!"
echo ""
echo "📋 Dependências instaladas:"
echo "   ✅ NumPy >= 1.21.0 (compatível com set_num_threads)"
echo "   ✅ PyTorch >= 1.13.0 (CPU otimizado)"
echo "   ✅ Whisper 20231117 (modelo de transcrição)"
echo "   ✅ Pydub 0.25.1 (processamento de áudio)"
echo "   ✅ FFmpeg Python (conversão de áudio)"
echo "   ✅ TQDM (barra de progresso)"
echo "   ✅ Tiktoken (tokenização)"
echo "   ✅ Numba (otimizações)"
echo "   ✅ Colorama (logs coloridos)"
echo ""
echo "🚀 Sistema pronto para transcrição otimizada!" 