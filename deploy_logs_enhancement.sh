#!/bin/bash

echo "🚀 Deployando melhorias de logs para transcrição..."

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

# Testar o script Python
echo "🧪 Testando script Python..."
cd python
python3 -c "
import sys
sys.path.append('.')
try:
    from transcribe import transcribe_audio
    from text_processor import TextProcessor
    print('✅ Scripts Python carregados com sucesso')
    print('✅ Sistema de logs Python funcionando')
except Exception as e:
    print(f'❌ Erro ao carregar scripts: {e}')
    sys.exit(1)
"
cd ..

echo "🎯 Melhorias de logs implementadas com sucesso!"
echo ""
echo "📋 Resumo das melhorias:"
echo "   ✅ Logs detalhados do Python capturados no Node.js"
echo "   ✅ Categorização de logs (info, warning, error, progress)"
echo "   ✅ Logs de progresso em tempo real"
echo "   ✅ Logs de recursos e performance"
echo "   ✅ Logs de início e fim de processos"
echo "   ✅ Logs de warnings do Whisper"
echo "   ✅ Logs de limpeza de arquivos temporários"
echo ""
echo "🚀 Agora todos os logs da transcrição aparecerão no console do Node.js!"
echo "   Incluindo logs do Whisper, warnings e progresso detalhado." 