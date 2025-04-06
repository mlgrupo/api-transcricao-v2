# Usar imagem com Node.js e Python já instalados
FROM nikolaik/python-nodejs:python3.12-nodejs18

# Definir variáveis de ambiente
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Definir diretório de trabalho
WORKDIR /app

# Atualizar e instalar FFmpeg em uma única camada
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copiar apenas arquivos de dependência para melhor caching
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# Copiar os arquivos Python e instalar dependências
COPY python/requirements.txt ./python/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r python/requirements.txt

# Copiar o resto do código
COPY . .

# Criar diretório temporário para os arquivos de processamento
RUN mkdir -p /app/temp && chmod 777 /app/temp

# Expor a porta que o servidor usa
EXPOSE 9898

# Comando para iniciar a aplicação
CMD ["node", "dist/server.js"]
