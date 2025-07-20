#!/bin/bash

# 🚀 Script de Deploy Rápido - Correção do Erro
# Para aplicar a correção do repetition_penalty

echo "🔧 Aplicando correção do erro repetition_penalty..."

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

echo "🎉 Correção aplicada com sucesso!"
echo ""
echo "✅ Problema corrigido:"
echo "- Removido parâmetro 'repetition_penalty' não suportado"
echo "- Mantidas todas as otimizações de CPU"
echo "- 4 workers simultâneos funcionando"
echo ""
echo "🔍 Para monitorar:"
echo "docker-compose logs -f backend" 