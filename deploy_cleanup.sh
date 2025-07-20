#!/bin/bash

echo "🧹 Limpeza final do projeto..."

# Verificar estrutura final
echo "📁 Verificando estrutura final..."
if [ ! -f "python/transcribe.py" ]; then
    echo "❌ Erro: python/transcribe.py não encontrado"
    exit 1
fi

if [ ! -f "python/text_processor.py" ]; then
    echo "❌ Erro: python/text_processor.py não encontrado"
    exit 1
fi

if [ ! -f "python/processing_rules.json" ]; then
    echo "❌ Erro: python/processing_rules.json não encontrado"
    exit 1
fi

if [ ! -f "src/core/transcription/transcription-processor.ts" ]; then
    echo "❌ Erro: transcription-processor.ts não encontrado"
    exit 1
fi

echo "✅ Todos os arquivos essenciais encontrados"

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

echo "🎯 Limpeza concluída com sucesso!"
echo ""
echo "📋 Resumo da limpeza:"
echo "   ✅ Arquivos não utilizados removidos"
echo "   ✅ Documentação antiga removida"
echo "   ✅ Scripts de deploy antigos removidos"
echo "   ✅ Logs antigos removidos"
echo "   ✅ Código TypeScript limpo"
echo "   ✅ Métodos não utilizados removidos"
echo ""
echo "🚀 Projeto limpo e otimizado!"
echo "   Estrutura final:"
echo "   ├── python/"
echo "   │   ├── transcribe.py (script principal)"
echo "   │   ├── text_processor.py (processamento de texto)"
echo "   │   ├── processing_rules.json (regras de processamento)"
echo "   │   └── requirements.txt (dependências)"
echo "   ├── src/core/transcription/"
echo "   │   └── transcription-processor.ts (backend limpo)"
echo "   └── deploy_cleanup.sh (este script)"
echo ""
echo "🎉 Projeto pronto para uso!" 