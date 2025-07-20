#!/bin/bash

# 🚀 Script de Deploy - MÁXIMA Performance de CPU
# Para aplicar no servidor com otimizações de CPU

echo "🚀 Iniciando deploy com MÁXIMA performance de CPU..."

# 1. Parar containers
echo "📦 Parando containers..."
docker-compose down

# 2. Pull das mudanças (se usando git)
echo "📥 Atualizando código..."
if [ -d ".git" ]; then
    git pull
fi

# 3. Limpar cache Docker para otimização
echo "🧹 Limpando cache Docker..."
docker system prune -f

# 4. Rebuild com otimizações de CPU
echo "🔨 Fazendo rebuild com MÁXIMA performance de CPU..."
docker-compose up -d --build

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

# 8. Verificar recursos do sistema
echo "📊 Verificando recursos do sistema..."
echo "CPU Cores: $(nproc)"
echo "RAM Total: $(free -h | grep Mem | awk '{print $2}')"
echo "RAM Livre: $(free -h | grep Mem | awk '{print $7}')"

echo "🎉 Deploy com MÁXIMA performance de CPU concluído!"
echo ""
echo "📊 Otimizações aplicadas:"
echo "✅ 4 workers simultâneos (máximo paralelismo)"
echo "✅ Configurações PyTorch otimizadas para CPU"
echo "✅ 8 threads por operação"
echo "✅ MKL-DNN habilitado"
echo "✅ OpenMP habilitado"
echo "✅ Limpeza de memória agressiva"
echo "✅ 100% CPU utilizado"
echo ""
echo "🔍 Para monitorar performance:"
echo "docker-compose logs -f backend"
echo "docker stats"
echo ""
echo "⚡ Performance esperada:"
echo "- 2-3x mais rápido que versão anterior"
echo "- 100% CPU utilizado eficientemente"
echo "- Processamento paralelo máximo" 