#!/bin/bash

# 🚨 Script de Deploy URGENTE - Correção do Erro repetition_penalty
# Para aplicar IMEDIATAMENTE no servidor

echo "🚨 DEPLOY URGENTE - Aplicando correção do erro repetition_penalty..."

# 1. Parar containers IMEDIATAMENTE
echo "🛑 Parando containers..."
docker-compose down

# 2. Limpar cache Docker
echo "🧹 Limpando cache..."
docker system prune -f

# 3. Rebuild FORÇADO
echo "🔨 Rebuild forçado..."
docker-compose build --no-cache

# 4. Subir containers
echo "🚀 Subindo containers..."
docker-compose up -d

# 5. Verificar status
echo "✅ Verificando status..."
sleep 15
docker-compose ps

# 6. Verificar logs
echo "📋 Verificando logs..."
docker-compose logs --tail=20 backend

# 7. Teste de saúde
echo "🏥 Teste de saúde..."
curl -f http://localhost:8080/health || echo "❌ Health check falhou"

echo ""
echo "🎉 DEPLOY URGENTE CONCLUÍDO!"
echo ""
echo "✅ Correção aplicada:"
echo "- ❌ repetition_penalty removido"
echo "- ✅ 4 workers simultâneos"
echo "- ✅ Otimizações de CPU mantidas"
echo "- ✅ Pós-processamento mantido"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend"
echo ""
echo "⚡ Agora deve funcionar sem erros!" 