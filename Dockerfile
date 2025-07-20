FROM nikolaik/python-nodejs:python3.11-nodejs18

WORKDIR /app

# Instala dependências do sistema otimizadas
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    libopenblas-dev \
    libomp-dev \
    libgomp1 \
    libgcc-s1 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copia pacotes e instala dependências Node.js
COPY package.json package-lock.json* ./
RUN npm install

ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Configurações otimizadas para performance
ENV OMP_NUM_THREADS=6
ENV OPENBLAS_NUM_THREADS=6
ENV MKL_NUM_THREADS=6
ENV NUMEXPR_NUM_THREADS=6
ENV PYTORCH_ENABLE_MPS_FALLBACK=1
ENV WHISPER_TURBO=0

# Configurações de memória para PyTorch
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Copia o restante do código
COPY . .

# Build do projeto Node.js
RUN npm run build

# Instala dependências Python otimizadas
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r python/requirements.txt

# Baixa o modelo Whisper large-v3 durante o build (otimizado)
RUN python -c "import whisper; whisper.load_model('large-v3')"

# Cria pasta temporária com permissão total
RUN mkdir -p /app/temp && chmod 777 /app/temp

# Configurações de recursos
ENV MAX_CONCURRENT_JOBS=2
ENV MAX_CPU_PERCENT=75
ENV MAX_MEMORY_GB=28

CMD ["sh", "-c", "npm start"]