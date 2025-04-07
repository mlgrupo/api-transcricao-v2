FROM nikolaik/python-nodejs:python3.12-nodejs18

# ⚠️ Coloca depois do npm install!
WORKDIR /app

# Instala ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia pacotes e instala tudo (incluindo tsup/typescript)
COPY package.json package-lock.json* ./
RUN npm install

# Agora sim, define o ambiente final
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Copia código
COPY . .

# Build com tsup
RUN npm run dist

# Python deps
COPY python/requirements.txt ./python/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r python/requirements.txt

# Pasta temporária
RUN mkdir -p /app/temp && chmod 777 /app/temp

EXPOSE 9898

CMD ["node", "dist/server.js"]
