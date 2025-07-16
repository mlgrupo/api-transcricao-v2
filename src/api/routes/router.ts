import { Express, RequestHandler } from 'express';
import { TranscriptionController } from '../controllers/Transcription-controller';
import { AuthController } from '../controllers/auth-controller';
import { DrivesController } from '../controllers/drives-controller';
import { ConfigController } from '../controllers/config-controller';
import { Logger } from '../../utils/logger';
import { VideoService } from '../../domain/services/video-service';
import { TranscriptionService } from '../../domain/services/transcription-service';
import { CollaboratorService } from '../../domain/services/collaborator-service';
import { ConfigRepository } from '../../data/repositories/config-repository';
import { GoogleAuthService } from '../../infrastructure/auth/google-auth';
import { authMiddleware, jwtAuthMiddleware } from '../middlewares/auth-middleware'
import { SystemController } from '../controllers/system-controller';
import asyncHandler from '../utils/asyncHandler';

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

  const drivesController = new DrivesController(
    collaboratorService,
    logger
  );

  const configRepository = new ConfigRepository(logger);
  const configController = new ConfigController(configRepository, logger);

  // Rotas de autenticação
  app.post('/auth/google/callback', authController.googleCallback.bind(authController));
  // @ts-ignore
  app.get('/auth/google/url', SystemController.getGoogleAuthUrl(googleAuthService));
  app.post('/auth/login', authController.login.bind(authController));
  // @ts-ignore
  app.get('/auth/me', jwtAuthMiddleware, AuthController.getMe);
  // @ts-ignore
  app.post('/auth/logout', jwtAuthMiddleware, SystemController.logout.bind(null));
  // @ts-ignore
  app.get('/auth/status', SystemController.authStatus.bind(null));

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

  // @ts-ignore
  app.get('/api/status', SystemController.apiStatus(transcriptionService));
  // @ts-ignore
  app.get('/health', SystemController.health.bind(null));

  // Rotas protegidas com JWT
  // @ts-ignore
  app.get('/videos', jwtAuthMiddleware, transcriptionController.getAllVideos.bind(transcriptionController));

  // Novas rotas para funcionalidades do frontend
  // @ts-ignore
  app.get('/api/videos/stats', jwtAuthMiddleware, transcriptionController.getVideoStats.bind(transcriptionController));
  // @ts-ignore
  app.get('/api/videos/:videoId/docx', jwtAuthMiddleware, transcriptionController.downloadTranscriptionDocx.bind(transcriptionController));
  // @ts-ignore
  app.post('/api/videos/:videoId/process-now', jwtAuthMiddleware, transcriptionController.processNow.bind(transcriptionController));
  // @ts-ignore
  app.post('/api/videos/:videoId/cancel', jwtAuthMiddleware, transcriptionController.cancelVideo.bind(transcriptionController));

  // Rotas de drives conectados
  // @ts-ignore
  app.get('/api/drives', jwtAuthMiddleware, drivesController.getConnectedDrives.bind(drivesController));
  // @ts-ignore
  app.post('/api/drives/:email/connect', jwtAuthMiddleware, drivesController.generateConnectionLink.bind(drivesController));
  // @ts-ignore
  app.delete('/api/drives/:email/disconnect', jwtAuthMiddleware, drivesController.disconnectDrive.bind(drivesController));

  // Rotas de configuração global
  app.get('/api/config/root-folder', jwtAuthMiddleware, asyncHandler(
    configController.getRootFolder.bind(configController)
  ));
  
  app.post('/api/config/root-folder', jwtAuthMiddleware, asyncHandler(
    configController.setRootFolder.bind(configController)
  ));
  // @ts-ignore
  app.get('/api/config/transcription', jwtAuthMiddleware, configController.getTranscriptionConfig.bind(configController));
  // @ts-ignore
  app.post('/api/config/transcription', jwtAuthMiddleware, configController.setTranscriptionConfig.bind(configController));
  // @ts-ignore
  app.get('/api/config/webhooks', jwtAuthMiddleware, configController.getWebhooks.bind(configController));
  // @ts-ignore
  app.post('/api/config/webhooks', jwtAuthMiddleware, configController.setWebhooks.bind(configController));
  // @ts-ignore
  app.post('/api/webhooks/test', jwtAuthMiddleware, configController.testWebhook.bind(configController));

  // Rotas de vídeo
  // @ts-ignore
  app.get('/api/videos', jwtAuthMiddleware, transcriptionController.getAllVideos.bind(transcriptionController));
  // @ts-ignore
  app.get('/api/videos/:videoId/status', jwtAuthMiddleware, transcriptionController.getVideoStatus.bind(transcriptionController));
  // @ts-ignore
  app.post('/api/videos/:videoId/reset', jwtAuthMiddleware, transcriptionController.resetQueueStatus.bind(transcriptionController));

  // Rota para criar usuário (apenas admin)
  app.post('/api/users', jwtAuthMiddleware, asyncHandler(
    authController.createUser.bind(authController)
  ));
};