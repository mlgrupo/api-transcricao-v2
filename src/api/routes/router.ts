import { Express } from 'express';
import { TranscriptionController } from '../controllers/Transcription-controller';
import { AuthController } from '../controllers/auth-controller';
import { Logger } from '../../utils/logger';
import { VideoService } from '../../domain/services/video-service';
import { TranscriptionService } from '../../domain/services/transcription-service';
import { CollaboratorService } from '../../domain/services/collaborator-service';
import { GoogleAuthService } from '../../infrastructure/auth/google-auth';
import { authMiddleware } from '../middlewares/auth-middleware'

export const setupRoutes = (
  app: Express,
  logger: Logger,
  videoService: VideoService,
  transcriptionService: TranscriptionService,
  collaboratorService: CollaboratorService
): void => {
  const googleAuthService = new GoogleAuthService(logger);
  const authController = new AuthController(
    googleAuthService, 
    collaboratorService, 
    logger
  );
  
  const transcriptionController = new TranscriptionController(
    transcriptionService,
    videoService,
    logger
  );

  // Rotas de autenticação
  app.post('/auth/google/callback', (req, res) => {
    console.log("entrou no google calllback")
    authController.googleCallback(req, res);
  });
  
  app.get('/auth/google/url', (_req, res) => {
    console.log("entrou na rota de autenticação google url")
    const authUrl = googleAuthService.getAuthUrl();
    res.json({ authUrl });
  });

  // Rotas protegidas com API Key
  app.post(
    '/api/transcribe',
    authMiddleware, 
    transcriptionController.transcribe.bind(transcriptionController)
  );

  app.get(
    '/api/pending-videos',
    authMiddleware,
    transcriptionController.getPendingVideos.bind(transcriptionController)
  );

  app.post(
    '/api/videos/:videoId/reset',
    authMiddleware, 
    transcriptionController.resetQueueStatus.bind(transcriptionController)
  );

  app.get(
    '/api/status',
    (_req, res) => {
      res.json({
        status: 'online',
        queueSize: transcriptionService.getQueueSize(),
        processing: transcriptionService.getProcessingSize(),
        version: process.env.npm_package_version || '1.0.0'
      });
    }
  );

  // Health check endpoint simples
  app.get('/health', (_req, res) => {
    res.json({ status: 'healthy' });
  });
};