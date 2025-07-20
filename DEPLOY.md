# 🚀 Guia de Deploy para Produção

Este guia explica como fazer o deploy da arquitetura robusta de transcrição no seu servidor.

## 📋 Pré-requisitos

- Servidor Linux (Ubuntu 20.04+ ou CentOS 8+)
- Mínimo 8 vCPUs e 32GB RAM
- 100GB de espaço em disco
- Acesso root ou sudo

## 🔧 Instalação Rápida

### 1. **Instalar dependências do sistema**
```bash
# Execute como root
sudo bash install-server.sh
```

### 2. **Configurar variáveis de ambiente**
```bash
# Copiar arquivo de exemplo
cp env.example .env

# Editar com suas configurações
nano .env
```

### 3. **Fazer deploy**
```bash
# Executar deploy
bash deploy-production.sh
```

## 📝 Configuração do .env

### Variáveis obrigatórias:
```bash
# Banco de dados
DB_HOST=postgres
DB_PORT=5432
DB_NAME=transcricao_db
DB_USER=postgres
DB_PASSWORD=sua_senha_segura

# Google Drive API
GOOGLE_CLIENT_ID=seu_client_id
GOOGLE_CLIENT_SECRET=seu_client_secret
GOOGLE_REDIRECT_URI=http://seu-dominio.com/auth/google/callback

# JWT
JWT_SECRET=sua_chave_jwt_super_secreta

# Servidor
NODE_ENV=production
PORT=8080
```

### Variáveis opcionais:
```bash
# Arquitetura robusta
HUGGING_FACE_TOKEN=seu_token_hf  # Para diarização avançada
MAX_CONCURRENT_JOBS=2
MAX_MEMORY_GB=28
MAX_CPU_PERCENT=90

# Processamento
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cpu
MAX_SPEAKERS=8
DIARIZATION_ENABLED=true
```

## 🐳 Comandos Docker

### Iniciar serviços:
```bash
docker-compose up -d
```

### Ver logs:
```bash
# Todos os serviços
docker-compose logs -f

# Apenas backend
docker-compose logs -f backend

# Apenas banco
docker-compose logs -f postgres
```

### Parar serviços:
```bash
docker-compose down
```

### Reiniciar:
```bash
docker-compose restart backend
```

### Reconstruir:
```bash
docker-compose build --no-cache
docker-compose up -d
```

## 🔍 Monitoramento

### Verificar status:
```bash
# Status dos containers
docker-compose ps

# Uso de recursos
docker stats

# Health check
curl http://localhost:8080/health
```

### Logs de aplicação:
```bash
# Logs em tempo real
docker-compose logs -f backend

# Últimas 100 linhas
docker-compose logs --tail=100 backend

# Logs com timestamp
docker-compose logs -f --timestamps backend
```

## 🛠️ Manutenção

### Backup do banco:
```bash
# Backup
docker-compose exec postgres pg_dump -U postgres transcricao_db > backup.sql

# Restore
docker-compose exec -T postgres psql -U postgres transcricao_db < backup.sql
```

### Limpeza:
```bash
# Limpar containers parados
docker container prune

# Limpar imagens não usadas
docker image prune

# Limpar volumes não usados
docker volume prune

# Limpeza completa
docker system prune -a
```

### Atualização:
```bash
# Parar serviços
docker-compose down

# Puxar código atualizado
git pull

# Reconstruir e iniciar
docker-compose build --no-cache
docker-compose up -d
```

## 🔧 Troubleshooting

### Problema: Container não inicia
```bash
# Verificar logs
docker-compose logs backend

# Verificar configuração
docker-compose config

# Verificar recursos
docker stats
```

### Problema: Erro de memória
```bash
# Aumentar swap
sudo fallocate -l 8G /swapfile2
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2

# Verificar uso de memória
free -h
```

### Problema: Erro de conexão com banco
```bash
# Verificar se PostgreSQL está rodando
docker-compose ps postgres

# Verificar logs do banco
docker-compose logs postgres

# Testar conexão
docker-compose exec postgres psql -U postgres -d transcricao_db
```

### Problema: Arquitetura robusta não funciona
```bash
# Verificar dependências Python
docker-compose exec backend python -c "import torch; print('PyTorch OK')"
docker-compose exec backend python -c "import librosa; print('Librosa OK')"

# Verificar modelos
docker-compose exec backend ls -la /app/python/models/

# Testar arquitetura robusta
docker-compose exec backend python /app/python/robust_transcription_adapter.py --status
```

## 📊 Performance

### Otimizações recomendadas:

1. **SSD**: Use SSD para melhor performance de I/O
2. **RAM**: Mínimo 32GB, recomendado 64GB
3. **CPU**: Mínimo 8 cores, recomendado 16 cores
4. **Rede**: Conexão estável de pelo menos 100Mbps

### Configurações de recursos:
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '8'
      memory: 32G
    reservations:
      cpus: '4'
      memory: 16G
```

## 🔒 Segurança

### Firewall:
```bash
# Permitir apenas portas necessárias
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8080/tcp  # API
sudo ufw deny 5432/tcp   # PostgreSQL (apenas local)
```

### SSL/TLS:
```bash
# Configurar nginx como proxy reverso
# Usar Let's Encrypt para certificados
```

### Backup:
```bash
# Backup automático diário
0 2 * * * /opt/transcricao/backup.sh
```

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs: `docker-compose logs -f`
2. Verifique recursos: `docker stats`
3. Teste componentes: `python robust_transcription_adapter.py --status`
4. Verifique configuração: `docker-compose config`

## 🎯 Próximos Passos

Após o deploy bem-sucedido:

1. Configure o Google Drive API
2. Teste upload de arquivos
3. Configure monitoramento
4. Configure backup automático
5. Configure SSL/TLS
6. Configure proxy reverso (opcional) 