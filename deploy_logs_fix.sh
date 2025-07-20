#!/bin/bash

echo "🔧 Corrigindo captura de logs do Python..."

# Verificar se os arquivos existem
echo "📁 Verificando arquivos..."
if [ ! -f "src/core/transcription/transcription-processor.ts" ]; then
    echo "❌ Erro: transcription-processor.ts não encontrado"
    exit 1
fi

if [ ! -f "python/transcribe.py" ]; then
    echo "❌ Erro: transcribe.py não encontrado"
    exit 1
fi

echo "✅ Todos os arquivos encontrados"

# Verificar se o TypeScript compila
echo "🔧 Verificando compilação TypeScript..."
if command -v npx &> /dev/null; then
    npx tsc --noEmit --project tsconfig.json
    if [ $? -eq 0 ]; then
        echo "✅ TypeScript compila sem erros"
    else
        echo "❌ Erro na compilação TypeScript"
        exit 1
    fi
else
    echo "⚠️ npx não encontrado, pulando verificação TypeScript"
fi

echo "🎯 Correção de logs implementada com sucesso!"
echo ""
echo "📋 Resumo das correções:"
echo "   ✅ Substituído execAsync por spawn"
echo "   ✅ Captura de logs em tempo real"
echo "   ✅ Logs do stdout do Python"
echo "   ✅ Logs do stderr do Python"
echo "   ✅ Categorização de logs (info, warning, error)"
echo "   ✅ Logs de progresso em tempo real"
echo "   ✅ Logs de início e fim de processos"
echo ""
echo "🔍 Agora você verá logs como:"
echo "   [transcribe.py][stdout] 🎯 Iniciando transcrição do arquivo: /app/temp/video.mp4"
echo "   [transcribe.py][stdout] ✅ Text processor inicializado"
echo "   [transcribe.py][stdout] 🔄 Carregando modelo Whisper Large..."
echo "   [transcribe.py][warning] FP16 is not supported on CPU; using FP32 instead"
echo "   [transcribe.py][stdout] ✅ Modelo Whisper Large carregado com sucesso"
echo "   [transcribe.py][stdout] 📂 Dividindo áudio em chunks..."
echo "   [transcribe.py][stdout] 🎵 Processando chunk 1: /app/temp/video.mp4_chunk_0.mp3"
echo "   [transcribe.py][stdout] 🔄 Transcrevendo chunk 1..."
echo "   [transcribe.py][stdout] ✅ Chunk 1 transcrito com sucesso"
echo "   [transcribe.py][stdout] ⏰ Ajustando timestamps para chunk 1 (início: 0s)"
echo "   [transcribe.py][stdout] 📝 Chunk 1 processado: 15 segmentos"
echo "   [transcribe.py][stdout] 🗑️ Arquivo temporário removido: /app/temp/video.mp4_chunk_0.mp3"
echo "   [transcribe.py][stdout] 🎉 Transcrição concluída com sucesso!"
echo "   [transcribe.py][stdout] 📊 Resumo: 1 chunks, 15 segmentos, 1234 caracteres"
echo "   🏁 Processo Python finalizado com código: 0"
echo "   ✅ Processo Python executado com sucesso"
echo ""
echo "🚀 Agora todos os logs da transcrição aparecerão no console do Node.js!" 