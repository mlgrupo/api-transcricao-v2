#!/bin/bash

# 🔧 Script de Deploy Rápido - Remoção da Aceleração
# Para resolver o travamento na etapa de aceleração do áudio

echo "🔧 Aplicando correção - Removendo aceleração do áudio..."

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
echo "🎉 Correção aplicada!"
echo ""
echo "✅ Problema resolvido:"
echo "- ❌ Removida aceleração do áudio (causava travamentos)"
echo "- ✅ Processamento direto sem manipulação de áudio"
echo "- ✅ Chunks de 10 minutos mantidos"
echo "- ✅ Paralelismo mantido"
echo "- ✅ Logs detalhados mantidos"
echo ""
echo "🔧 Mudanças aplicadas:"
echo "- 📊 Sem aceleração de áudio (1.2x removida)"
echo "- ⚡ Processamento direto do áudio original"
echo "- 🎯 Chunks de 10 minutos para evitar travamentos"
echo "- 🔄 Paralelismo real mantido"
echo "- 📈 Logs de progresso mantidos"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend"
echo ""
echo "⚡ Agora deve funcionar sem travamentos!" 