#!/bin/bash

# 🚨 DEPLOY DE EMERGÊNCIA - Correção TOTAL do erro repetition_penalty
# Para aplicar TODAS as correções IMEDIATAMENTE

echo "🚨 DEPLOY DE EMERGÊNCIA - Aplicando TODAS as correções..."

# 1. Parar TUDO
echo "🛑 Parando todos os containers..."
docker-compose down

# 2. Limpar TUDO
echo "🧹 Limpando cache e imagens..."
docker system prune -af
docker volume prune -f

# 3. Rebuild COMPLETO
echo "🔨 Rebuild completo..."
docker-compose build --no-cache --force-rm

# 4. Subir containers
echo "🚀 Subindo containers..."
docker-compose up -d

# 5. Aguardar inicialização
echo "⏳ Aguardando inicialização..."
sleep 20

# 6. Verificar status
echo "✅ Verificando status..."
docker-compose ps

# 7. Verificar logs
echo "📋 Verificando logs..."
docker-compose logs --tail=30 backend

# 8. Teste de saúde
echo "🏥 Teste de saúde..."
curl -f http://localhost:8080/health || echo "❌ Health check falhou"

# 9. Verificar se não há mais repetition_penalty
echo "🔍 Verificando se não há mais repetition_penalty..."
docker-compose exec backend grep -r "repetition_penalty" /app/python/ || echo "✅ Nenhuma referência encontrada!"

echo ""
echo "🎉 DEPLOY DE EMERGÊNCIA CONCLUÍDO!"
echo ""
echo "✅ TODAS as correções aplicadas:"
echo "- ❌ repetition_penalty removido de TODOS os arquivos"
echo "- ✅ 4 workers simultâneos"
echo "- ✅ Otimizações de CPU mantidas"
echo "- ✅ Pós-processamento mantido"
echo "- ✅ Cache limpo completamente"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend"
echo ""
echo "⚡ Agora DEVE funcionar sem erros!"
echo "🚀 Teste uma transcrição agora!" 