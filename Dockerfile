# Etapa base com Node.js + Python
FROM nikolaik/python-nodejs:python3.12-nodejs18

# Variáveis de ambiente
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Diretório de trabalho
WORKDIR /app

# FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Instala dependências Node.js (inclui tsup, typescript etc)
COPY package.json package-lock.json* ./
RUN npm install

# Copia tudo (src, tsconfig, etc.)
COPY . .

# Builda a aplicação com tsup (gera dist/)
RUN npm run dist

# Instala dependências Python
COPY python/requirements.txt ./python/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r python/requirements.txt

# Pasta temporária
RUN mkdir -p /app/temp && chmod 777 /app/temp

# Expor porta
EXPOSE 9898

# Iniciar app (agora que dist/server.js existe)
CMD ["node", "dist/server.js"]
