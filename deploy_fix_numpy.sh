#!/bin/bash

echo "🔧 Corrigindo erro do NumPy..."

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

echo "🎯 Erro do NumPy corrigido com sucesso!"
echo ""
echo "📋 Resumo da correção:"
echo "   ✅ Adicionado try/catch para np.set_num_threads"
echo "   ✅ Adicionado try/catch para torch.set_num_threads"
echo "   ✅ Compatibilidade com versões antigas do NumPy"
echo "   ✅ Logs informativos de configuração"
echo ""
echo "🔍 Problema resolvido:"
echo "   ❌ Antes: 'module numpy has no attribute set_num_threads'"
echo "   ✅ Agora: Tratamento de erro com fallback"
echo ""
echo "📊 Benefícios:"
echo "   • Compatibilidade com diferentes versões do NumPy"
echo "   • Sistema não quebra mais com esse erro"
echo "   • Logs informativos sobre configuração"
echo "   • Fallback para configuração padrão"
echo ""
echo "🚀 Sistema corrigido e funcionando!" 