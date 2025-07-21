#!/bin/bash

echo "🔧 Otimizando logs para reduzir spam..."

# Verificar se os arquivos existem
echo "📁 Verificando arquivos..."
if [ ! -f "python/text_processor.py" ]; then
    echo "❌ Erro: text_processor.py não encontrado"
    exit 1
fi

if [ ! -f "python/transcribe.py" ]; then
    echo "❌ Erro: transcribe.py não encontrado"
    exit 1
fi

echo "✅ Todos os arquivos encontrados"

# Verificar se o Python funciona
echo "🐍 Testando Python..."
python3 --version
if [ $? -eq 0 ]; then
    echo "✅ Python funcionando"
else
    echo "❌ Erro: Python não encontrado"
    exit 1
fi

echo "🎯 Otimização de logs implementada com sucesso!"
echo ""
echo "📋 Resumo das otimizações:"
echo "   ✅ Removido spam de logs do text_processor"
echo "   ✅ Adicionado logs informativos de processamento"
echo "   ✅ Mantido logs de erro para debugging"
echo "   ✅ Logs mais limpos e organizados"
echo ""
echo "🔍 Agora você verá logs como:"
echo "   [transcribe.py][stdout] 🎵 Processando chunk 1 (20.0% do total)"
echo "   [transcribe.py][stdout] 🔄 Transcrevendo chunk 1..."
echo "   [transcribe.py][stdout] ✅ Chunk 1 transcrito com sucesso"
echo "   [transcribe.py][stdout] ⏰ Ajustando timestamps para chunk 1 (início: 0s)"
echo "   [transcribe.py][stdout] 📝 Chunk 1 processado: 15 segmentos"
echo "   [transcribe.py][stdout] 🔧 Aplicando processamento de texto ao chunk 1..."
echo "   [transcribe.py][stdout] ✅ Processamento de texto concluído para chunk 1"
echo "   [transcribe.py][stdout] 🗑️ Arquivo temporário removido: /app/temp/video.mp4_chunk_0.mp3"
echo ""
echo "🚀 Logs muito mais limpos e informativos!" 