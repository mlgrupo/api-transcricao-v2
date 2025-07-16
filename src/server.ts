import 'reflect-metadata'; // Adicione esta linha no início
import express from 'express';
import cors from 'cors';
import { rateLimit } from 'express-rate-limit';
import { appPromise } from './application';
import { setupRoutes } from './api/routes/router';
import { initializeDevSeed } from './data/seed-manager';

const expressApp = express();
const PORT = process.env.PORT || 3001;

// Configurar trust proxy
expressApp.set('trust proxy', 'loopback, linklocal, uniquelocal');

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100
});

// CORS dinâmico por variável de ambiente
const corsOrigins = process.env.CORS_ORIGIN
  ? process.env.CORS_ORIGIN.split(',').map(origin => origin.trim())
  : ['http://localhost:3000'];

// Middlewares
expressApp.use(cors({
  origin: (origin, callback) => {
    // Permite requests sem origin (ex: Postman) ou se estiver na lista
    if (!origin || corsOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true
}));
expressApp.use(express.json());
expressApp.use(limiter);

// Global error handler
expressApp.use((err: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

async function startServer() {
  try {
    // Inicializar aplicação primeiro (isso garante que o DataSource seja inicializado)
    const app = await appPromise;
    await app.initialize();
    
    // Agora que o DataSource está inicializado, podemos executar o seed

    // Calcular data limite (1 dia antes da inicialização)
    const creationDateFilter = new Date();
    creationDateFilter.setDate(creationDateFilter.getDate() - 1);
    app.logger.info(`Setting drive watcher threshold date to: ${creationDateFilter.toISOString()}`);
    if (app.driveWatcher) {
      app.driveWatcher.setThresholdDate(creationDateFilter);
    }

    // Configurar rotas
    expressApp.set('collaboratorService', app.collaboratorService);
    setupRoutes(
      expressApp,
      app.logger,
      app.videoService,
      app.transcriptionService,
      app.collaboratorService
    );

    // Iniciar servidor HTTP
    expressApp.listen(PORT, () => {
      app.logger.info(`🚀 Servidor rodando na porta ${PORT}`);
      app.logger.info('🔄 Sistema de transcrição iniciado com sucesso');
    });
  } catch (error: any) {
    console.error('❌ Erro ao iniciar servidor:', error);
    process.exit(1);
  }
}

startServer();
