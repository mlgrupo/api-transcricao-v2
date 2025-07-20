#!/bin/bash

# === SCRIPT DE INSTALAÇÃO PARA SERVIDOR ===
# Este script instala todas as dependências necessárias

set -e

echo "🚀 Iniciando instalação no servidor..."

# Verificar se é root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️ Execute este script como root ou com sudo"
    exit 1
fi

# Detectar distribuição Linux
if [ -f /etc/debian_version ]; then
    DISTRO="debian"
elif [ -f /etc/redhat-release ]; then
    DISTRO="redhat"
elif [ -f /etc/centos-release ]; then
    DISTRO="centos"
else
    echo "❌ Distribuição Linux não suportada"
    exit 1
fi

echo "📦 Distribuição detectada: $DISTRO"

# Atualizar sistema
echo "🔄 Atualizando sistema..."
if [ "$DISTRO" = "debian" ]; then
    apt-get update && apt-get upgrade -y
elif [ "$DISTRO" = "redhat" ] || [ "$DISTRO" = "centos" ]; then
    yum update -y
fi

# Instalar dependências básicas
echo "📦 Instalando dependências básicas..."
if [ "$DISTRO" = "debian" ]; then
    apt-get install -y \
        curl \
        wget \
        git \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release
elif [ "$DISTRO" = "redhat" ] || [ "$DISTRO" = "centos" ]; then
    yum install -y \
        curl \
        wget \
        git \
        unzip \
        yum-utils \
        device-mapper-persistent-data \
        lvm2
fi

# Instalar Docker
echo "🐳 Instalando Docker..."
if ! command -v docker &> /dev/null; then
    if [ "$DISTRO" = "debian" ]; then
        # Adicionar repositório Docker
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io
    elif [ "$DISTRO" = "redhat" ] || [ "$DISTRO" = "centos" ]; then
        yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        yum install -y docker-ce docker-ce-cli containerd.io
    fi
    
    # Iniciar e habilitar Docker
    systemctl start docker
    systemctl enable docker
else
    echo "✅ Docker já está instalado"
fi

# Instalar Docker Compose
echo "🐳 Instalando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "✅ Docker Compose já está instalado"
fi

# Criar usuário para aplicação (opcional)
echo "👤 Criando usuário para aplicação..."
if ! id "transcricao" &>/dev/null; then
    useradd -m -s /bin/bash transcricao
    usermod -aG docker transcricao
    echo "✅ Usuário 'transcricao' criado"
else
    echo "✅ Usuário 'transcricao' já existe"
fi

# Criar diretórios necessários
echo "📁 Criando diretórios..."
mkdir -p /opt/transcricao
mkdir -p /opt/transcricao/logs
mkdir -p /opt/transcricao/temp
mkdir -p /opt/transcricao/models
mkdir -p /opt/transcricao/outputs

# Definir permissões
chown -R transcricao:transcricao /opt/transcricao
chmod -R 755 /opt/transcricao

# Configurar firewall (se necessário)
echo "🔥 Configurando firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp
    ufw allow 8080/tcp
    ufw allow 5432/tcp
    ufw --force enable
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=22/tcp
    firewall-cmd --permanent --add-port=8080/tcp
    firewall-cmd --permanent --add-port=5432/tcp
    firewall-cmd --reload
fi

# Configurar swap (se necessário)
echo "💾 Configurando swap..."
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "✅ Swap configurado (4GB)"
else
    echo "✅ Swap já está configurado"
fi

# Configurar limites do sistema
echo "⚙️ Configurando limites do sistema..."
cat >> /etc/security/limits.conf << EOF
# Limites para aplicação de transcrição
transcricao soft nofile 65536
transcricao hard nofile 65536
transcricao soft nproc 32768
transcricao hard nproc 32768
EOF

# Configurar sysctl
echo "⚙️ Configurando sysctl..."
cat >> /etc/sysctl.conf << EOF
# Configurações para aplicação de transcrição
vm.max_map_count=262144
fs.file-max=65536
net.core.somaxconn=65535
EOF

sysctl -p

echo "🎉 Instalação concluída!"
echo ""
echo "📋 Próximos passos:"
echo "1. Copie os arquivos do projeto para /opt/transcricao"
echo "2. Configure o arquivo .env baseado no env.example"
echo "3. Execute: cd /opt/transcricao && ./deploy-production.sh"
echo ""
echo "🔧 Comandos úteis:"
echo "   - Verificar Docker: docker --version"
echo "   - Verificar Docker Compose: docker-compose --version"
echo "   - Verificar usuário: id transcricao"
echo "   - Verificar swap: free -h" 