# Etapa de build
FROM node:18 as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run dist

# Etapa final
FROM nikolaik/python-nodejs:python3.12-nodejs18
WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY python/requirements.txt ./python/
RUN pip install --upgrade pip && pip install -r python/requirements.txt

COPY --from=builder /app/dist ./dist
COPY . .

EXPOSE 9898
CMD ["node", "dist/server.js"]
