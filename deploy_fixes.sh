#!/bin/bash

# 🚀 Script de Deploy - Correções de Timestamps e Otimizações
# Para aplicar no servidor externo

echo "🚀 Iniciando deploy das correções..."

# 1. Parar containers
echo "📦 Parando containers..."
docker-compose down

# 2. Pull das mudanças (se usando git)
echo "📥 Atualizando código..."
if [ -d ".git" ]; then
    git pull
fi

# 3. Rebuild com as correções
echo "🔨 Fazendo rebuild com correções..."
docker-compose up -d --build

# 4. Verificar status
echo "✅ Verificando status..."
sleep 10
docker-compose ps

# 5. Verificar logs
echo "📋 Verificando logs..."
docker-compose logs --tail=20 backend

# 6. Teste de saúde
echo "🏥 Teste de saúde..."
curl -f http://localhost:8080/health || echo "❌ Health check falhou"

echo "🎉 Deploy das correções concluído!"
echo ""
echo "📊 Correções aplicadas:"
echo "✅ Erro de sintaxe corrigido (caracteres especiais)"
echo "✅ Timestamps habilitados (segmentos + palavras)"
echo "✅ Chunks de 5 minutos mantidos"
echo "✅ Otimizações de velocidade mantidas"
echo "✅ 100% recursos utilizados"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend" 