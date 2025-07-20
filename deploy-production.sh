#!/bin/bash

# === SCRIPT DE DEPLOY PARA PRODUÇÃO ===
# Este script configura e inicia o sistema no servidor

set -e  # Para em caso de erro

echo "🚀 Iniciando deploy de produção..."

# Verificar se Docker está instalado
if ! command -v docker &> /dev/null; then
    echo "❌ Docker não está instalado. Instale o Docker primeiro."
    exit 1
fi

# Verificar se Docker Compose está instalado
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose não está instalado. Instale o Docker Compose primeiro."
    exit 1
fi

# Verificar se arquivo .env existe
if [ ! -f .env ]; then
    echo "❌ Arquivo .env não encontrado. Crie o arquivo .env com as variáveis necessárias."
    exit 1
fi

echo "✅ Verificações básicas passaram"

# Parar containers existentes
echo "🛑 Parando containers existentes..."
docker-compose down --remove-orphans

# Limpar imagens antigas (opcional)
echo "🧹 Limpando imagens antigas..."
docker system prune -f

# Construir nova imagem
echo "🔨 Construindo nova imagem..."
docker-compose build --no-cache

# Iniciar serviços
echo "🚀 Iniciando serviços..."
docker-compose up -d

# Aguardar serviços ficarem prontos
echo "⏳ Aguardando serviços ficarem prontos..."
sleep 30

# Verificar status dos serviços
echo "🔍 Verificando status dos serviços..."
docker-compose ps

# Verificar logs
echo "📋 Últimos logs do backend:"
docker-compose logs --tail=20 backend

# Verificar health check
echo "🏥 Verificando health check..."
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Health check passou!"
else
    echo "⚠️ Health check falhou. Verifique os logs."
fi

echo "🎉 Deploy concluído!"
echo ""
echo "📊 Informações do sistema:"
echo "   - Backend: http://localhost:8080"
echo "   - PostgreSQL: localhost:5432"
echo "   - Logs: docker-compose logs -f"
echo "   - Status: docker-compose ps"
echo ""
echo "🔧 Comandos úteis:"
echo "   - Parar: docker-compose down"
echo "   - Logs: docker-compose logs -f backend"
echo "   - Restart: docker-compose restart backend" 