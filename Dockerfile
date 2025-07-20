FROM nikolaik/python-nodejs:python3.11-nodejs18

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libportaudio2 \
    portaudio19-dev \
    python3-dev \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia pacotes e instala dependências Node.js
COPY package.json package-lock.json* ./
RUN npm install

# Define variáveis de ambiente
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app/python

# Copia o restante do código
COPY . .

# Build do projeto Node.js
RUN npm run build

# Instala dependências Python básicas
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r python/requirements.txt

# Instala PyTorch CPU (otimizado para servidor)
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Instala dependências da arquitetura robusta
RUN pip install --no-cache-dir -r python/requirements-robust.txt

# Instala dependências adicionais necessárias
RUN pip install --no-cache-dir \
    faster-whisper \
    pyannote.core \
    pyannote.metrics \
    resampy \
    audioread \
    multiprocessing-logging

# Cria pastas necessárias com permissões
RUN mkdir -p /app/temp && \
    mkdir -p /app/python/models && \
    mkdir -p /app/python/outputs && \
    chmod 777 /app/temp && \
    chmod 777 /app/python/models && \
    chmod 777 /app/python/outputs

# Exponha a porta
EXPOSE 8080

# Starta o servidor
CMD ["sh", "-c", "npm start"]