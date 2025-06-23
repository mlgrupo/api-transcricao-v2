FROM nikolaik/python-nodejs:python3.12-nodejs18

WORKDIR /app

# Instala ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia pacotes e instala dependências Node.js
COPY package.json package-lock.json* ./
RUN npm install

# Define variáveis de ambiente
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Copia o restante do código
COPY . .

# Build do projeto Node.js
RUN npm run dist

# Instala dependências Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r python/requirements.txt

# Cria pasta temporária com permissão total
RUN mkdir -p /app/temp && chmod 777 /app/temp

# Exponha a porta (Railway usa a variável PORT, mas expor 8080 é padrão)
EXPOSE 8080

# Starta o servidor (usa a porta definida pelo Railway)
CMD ["node", "dist/server.js"]