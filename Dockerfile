FROM nikolaik/python-nodejs:python3.11-nodejs18

WORKDIR /app

# Instala ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg libopenblas-dev libomp-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia pacotes e instala dependências Node.js
COPY package.json package-lock.json* ./
RUN npm install

ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV PYTORCH_ENABLE_MPS_FALLBACK=1

# Copia o restante do código
COPY . .

# Build do projeto Node.js
RUN npm run build

# Instala dependências Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r python/requirements.txt

# Baixa o modelo Whisper large durante o build
RUN python -c "import whisper; whisper.load_model('large')"

# Cria pasta temporária com permissão total
RUN mkdir -p /app/temp && chmod 777 /app/temp

CMD ["sh", "-c", "npm start"]