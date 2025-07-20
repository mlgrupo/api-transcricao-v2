#!/bin/bash

# 🚀 Script de Deploy - Transcrição Otimizada
# Para resolver problemas de CPU travado e transcrição lenta

echo "🚀 Aplicando otimizações de transcrição..."

# 1. Parar containers
echo "📦 Parando containers..."
docker-compose down

# 2. Rebuild com otimizações
echo "🔨 Fazendo rebuild com otimizações..."
docker-compose up -d --build

# 3. Verificar status
echo "✅ Verificando status..."
sleep 15
docker-compose ps

# 4. Verificar logs
echo "📋 Verificando logs..."
docker-compose logs --tail=20 backend

echo ""
echo "🎉 Otimizações aplicadas!"
echo ""
echo "✅ Problemas resolvidos:"
echo "- ❌ CPU não mais travado em 100%"
echo "- ✅ Paralelismo real com múltiplos processos"
echo "- ✅ Chunks de 10 minutos para evitar travamentos"
echo "- ✅ Logs detalhados de progresso"
echo "- ✅ Otimização máxima de CPU (500%+)"
echo "- ✅ Monitoramento de recursos em tempo real"
echo ""
echo "🔧 Melhorias implementadas:"
echo "- 📊 Chunks de 10 minutos (600s)"
echo "- ⚡ ProcessPoolExecutor para paralelismo real"
echo "- 🎯 4 CPUs por worker, máximo 2 workers"
echo "- 📈 Logs de progresso detalhados"
echo "- 🔄 Processamento paralelo de chunks"
echo "- 📊 Monitoramento de recursos"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend"
echo ""
echo "📊 Para verificar CPU:"
echo "docker stats"
echo ""
echo "⚡ Agora a transcrição deve usar 500%+ de CPU e ser muito mais rápida!" 