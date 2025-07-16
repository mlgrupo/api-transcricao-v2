import { Request, Response } from 'express';
import { GoogleAuthService } from '../../infrastructure/auth/google-auth';
import { TranscriptionService } from '../../domain/services/transcription-service';

export class SystemController {
  static getGoogleAuthUrl(googleAuthService: GoogleAuthService) {
    return (req: Request, res: Response): void => {
      const authUrl = googleAuthService.getAuthUrl();
      res.json({ authUrl });
    };
  }

  static getMe(req: Request, res: Response): void {
    const user = (req as any).user;
    if (user) {
      res.json({
        id: user.userId || 1,
        name: user.name || user.email || 'Usuário',
        email: user.email,
        isAdmin: user.isAdmin || false,
        avatarUrl: user.picture || null,
        driveConnected: true
      });
    } else {
      res.status(401).json({ error: 'Usuário não autenticado' });
    }
  }

  static logout(req: Request, res: Response): void {
    res.json({ message: 'Logout realizado com sucesso' });
  }

  static authStatus(req: Request, res: Response): void {
    res.status(401).json({ user: null });
  }

  static apiStatus(transcriptionService: TranscriptionService) {
    return (req: Request, res: Response): void => {
      res.json({
        status: 'online',
        queueSize: transcriptionService.getQueueSize(),
        processing: transcriptionService.getProcessingSize(),
        version: process.env.npm_package_version || '1.0.0'
      });
    };
  }

  static health(_req: Request, res: Response): void {
    res.json({ status: 'healthy' });
  }
} 