#!/bin/bash

# 🔧 Script de Deploy Rápido - Correção dos Logs
# Para corrigir logs que aparecem como erro quando são apenas progresso

echo "🔧 Aplicando correção dos logs..."

# 1. Parar containers
echo "📦 Parando containers..."
docker-compose down

# 2. Rebuild rápido
echo "🔨 Fazendo rebuild rápido..."
docker-compose up -d --build

# 3. Verificar status
echo "✅ Verificando status..."
sleep 10
docker-compose ps

# 4. Verificar logs
echo "📋 Verificando logs..."
docker-compose logs --tail=10 backend

echo ""
echo "🎉 Correção dos logs aplicada!"
echo ""
echo "✅ Problema corrigido:"
echo "- ❌ Logs de progresso não aparecem mais como erro"
echo "- ✅ Apenas erros reais aparecem como error"
echo "- ✅ Logs de progresso aparecem como info"
echo "- ✅ Melhor visualização do progresso"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend"
echo ""
echo "⚡ Agora os logs aparecem corretamente!" 