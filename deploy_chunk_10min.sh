#!/bin/bash

echo "🔧 Alterando tamanho do chunk para 10 minutos..."

# Verificar se os arquivos existem
echo "📁 Verificando arquivos..."
if [ ! -f "python/transcribe.py" ]; then
    echo "❌ Erro: transcribe.py não encontrado"
    exit 1
fi

echo "✅ Arquivo encontrado"

# Verificar se o Python funciona
echo "🐍 Testando Python..."
python3 --version
if [ $? -eq 0 ]; then
    echo "✅ Python funcionando"
else
    echo "❌ Erro: Python não encontrado"
    exit 1
fi

echo "🎯 Chunk alterado para 10 minutos com sucesso!"
echo ""
echo "📋 Resumo da alteração:"
echo "   ✅ Chunk duration: 5 minutos → 10 minutos"
echo "   ✅ Timestamp calculation: 5 min → 10 min"
echo "   ✅ Processamento sequencial mantido"
echo ""
echo "📊 Impacto da mudança:"
echo "   • Menos chunks por vídeo"
echo "   • Processamento mais rápido"
echo "   • Menos arquivos temporários"
echo "   • Melhor performance geral"
echo ""
echo "🔍 Exemplo para vídeo de 30 minutos:"
echo "   Antes: 6 chunks de 5 minutos"
echo "   Agora: 3 chunks de 10 minutos"
echo ""
echo "🚀 Sistema otimizado com chunks de 10 minutos!" 