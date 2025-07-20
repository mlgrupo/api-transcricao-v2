#!/bin/bash

# 🚀 Script de Deploy - Solução Simples e Robusta
# Transcrição sem chunks, modelo large, 1.2x velocidade

echo "🚀 Iniciando deploy da solução SIMPLES e ROBUSTA..."

# 1. Parar containers
echo "📦 Parando containers..."
docker-compose down

# 2. Limpar cache
echo "🧹 Limpando cache..."
docker system prune -f

# 3. Rebuild
echo "🔨 Fazendo rebuild..."
docker-compose up -d --build

# 4. Verificar status
echo "✅ Verificando status..."
sleep 15
docker-compose ps

# 5. Verificar logs
echo "📋 Verificando logs..."
docker-compose logs --tail=20 backend

# 6. Teste de saúde
echo "🏥 Teste de saúde..."
curl -f http://localhost:8080/health || echo "❌ Health check falhou"

echo ""
echo "🎉 Deploy da solução SIMPLES concluído!"
echo ""
echo "✅ Nova solução implementada:"
echo "- 🎯 Audio inteiro sem cortar"
echo "- 🎯 Modelo 'large' para máxima qualidade"
echo "- ⚡ 1.2x de velocidade"
echo "- 🔧 4 CPUs por worker, máximo 2 workers"
echo "- 💾 13GB RAM por worker"
echo "- ✨ Pós-processamento integrado"
echo "- 🚫 Sem chunks (evita erros de divisão)"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend"
echo ""
echo "⚡ Agora deve funcionar sem erros de chunks!" 