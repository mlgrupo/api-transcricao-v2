import { Request, Response } from "express";
import { Logger } from "../../utils/logger";
import { TranscriptionService } from "../../domain/services/transcription-service";
import { VideoService } from "../../domain/services/video-service";
import { Document, Packer, Paragraph, TextRun } from 'docx';
import type { Video } from '../../domain/models/Video';

export class TranscriptionController {
  constructor(
    private transcriptionService: TranscriptionService,
    private videoService: VideoService,
    private logger: Logger
  ) {}

  public async transcribe(req: Request, res: Response): Promise<void> {
    try {
      const { videoId, email, webhook_url, folder_id } = req.body;

      if (!videoId || !email) {
        res.status(400).json({
          success: false,
          error: "Missing required parameters: videoId and email are required",
        });
        return;
      }

      const webhookUrl = webhook_url || process.env.WEBHOOK_URL;
      
      // Generate a unique task ID for this job
      const taskId = `${Date.now()}-${videoId}`;
      
      // Queue the video for transcription
      await this.transcriptionService.enqueueVideo({
        taskId,
        videoId,
        email,
        webhookUrl,
        folderId: folder_id,
      });

      // Mark as queued in database
      await this.videoService.markVideoAsQueued(videoId);

      res.status(200).json({
        success: true,
        message: `Video ${videoId} queued for transcription`,
        taskId,
      });
    } catch (error: any) {
      this.logger.error("Error queuing video for transcription:", error);
      res.status(500).json({
        success: false,
        error: error.message,
      });
    }
  }

  public async getPendingVideos(req: Request, res: Response): Promise<void> {
    try {
      const limit = req.query.limit ? parseInt(req.query.limit as string) : 10;
      const pendingVideos = await this.videoService.getPendingVideos(limit);
      
      res.status(200).json({
        success: true,
        count: pendingVideos.length,
        videos: pendingVideos,
      });
    } catch (error: any) {
      this.logger.error("Error getting pending videos:", error);
      res.status(500).json({
        success: false,
        error: error.message,
      });
    }
  }

  public async resetQueueStatus(req: Request, res: Response): Promise<void> {
    try {
      const { videoId } = req.params;
      
      if (!videoId) {
        res.status(400).json({
          success: false,
          error: "Missing videoId parameter",
        });
        return;
      }

      this.logger.info(`Resetando status de fila para o vídeo: ${videoId}`);
      
      // Reset the queue status and re-enqueue
      const result = await this.videoService.resetQueueStatus(videoId);
      
      res.status(200).json({
        ...result,
        success: true
      });
    } catch (error: any) {
      this.logger.error(`Erro ao resetar status de fila do vídeo ${req.params.videoId}:`, error);
      
      // Avoid sending headers multiple times
      if (!res.headersSent) {
        res.status(500).json({
          success: false,
          error: error.message,
        });
      }
    }
  }

  public async getAllVideos(req: Request, res: Response): Promise<void> {
    try {
      // Verifica se o usuário é admin
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: 'Acesso restrito a administradores.' });
        return;
      }
      const videos = await this.videoService.getAllVideos();
      res.status(200).json(videos);
    } catch (error: any) {
      this.logger.error('Erro ao buscar todos os vídeos:', error);
      res.status(500).json({ error: error.message });
    }
  }

  public async getVideoStats(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.userId) {
        res.status(401).json({ error: 'Usuário não autenticado' });
        return;
      }
      const stats = await this.videoService.getVideoStats(user.userId);
      res.status(200).json(stats);
    } catch (error: any) {
      this.logger.error('Erro ao buscar estatísticas dos vídeos:', error);
      res.status(500).json({ error: error.message });
    }
  }

  public async getVideoStatus(req: Request, res: Response): Promise<void> {
    try {
      const { videoId } = req.params;
      
      if (!videoId) {
        res.status(400).json({ error: 'ID do vídeo é obrigatório' });
        return;
      }

      const video = await this.videoService.getVideoById(videoId);
      
      if (!video) {
        res.status(404).json({ error: 'Vídeo não encontrado' });
        return;
      }

      res.status(200).json({
        videoId: video.videoId,
        videoName: video.videoName,
        status: video.status,
        progress: video.progress || 0,
        etapaAtual: video.etapaAtual || 'Não iniciado',
        transcrito: video.transcrito,
        enfileirado: video.enfileirado,
        errorMessage: video.errorMessage,
        dtCriacao: video.dtCriacao,
        dtAtualizacao: video.dtAtualizacao
      });
    } catch (error: any) {
      this.logger.error('Erro ao buscar status do vídeo:', error);
      res.status(500).json({ error: error.message });
    }
  }

  /**
   * Gera e faz download do DOCX da transcrição de um vídeo (apenas admin)
   */
  public async downloadTranscriptionDocx(req: Request, res: Response): Promise<void> {
    try {
      // Verifica se o usuário é admin
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: 'Acesso restrito a administradores.' });
        return;
      }
      const { videoId } = req.params;
      if (!videoId) {
        res.status(400).json({ error: 'ID do vídeo é obrigatório.' });
        return;
      }
      const video: Video | null = await this.videoService.getVideoById(videoId);
      if (!video) {
        res.status(404).json({ error: 'Vídeo não encontrado.' });
        return;
      }
      if (!video.transcrito || typeof video.transcrito !== 'string' || video.transcrito.trim().length === 0) {
        res.status(404).json({ error: 'Transcrição não encontrada para este vídeo.' });
        return;
      }
      const transcription: string = video.transcrito;
      // Gerar DOCX em memória
      const doc = new Document({
        sections: [
          {
            properties: {},
            children: [
              new Paragraph({
                children: [
                  new TextRun({ text: `Transcrição do vídeo: ${video.videoName || videoId}`, bold: true, size: 28 }),
                ],
              }),
              new Paragraph({ text: '' }),
              ...transcription.split('\n').map((line: string) => new Paragraph(line)),
            ],
          },
        ],
      });
      const buffer = await Packer.toBuffer(doc);
      res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
      res.setHeader('Content-Disposition', `attachment; filename="transcricao_${videoId}.docx"`);
      res.send(buffer);
    } catch (error: any) {
      this.logger.error('Erro ao gerar DOCX da transcrição:', error);
      res.status(500).json({ error: error.message });
    }
  }

  /**
   * Processa imediatamente um vídeo (admin)
   */
  public async processNow(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: 'Acesso restrito a administradores.' });
        return;
      }
      const { videoId } = req.params;
      if (!videoId) {
        res.status(400).json({ error: 'ID do vídeo é obrigatório.' });
        return;
      }
      // Buscar vídeo
      const video = await this.videoService.getVideoById(videoId);
      if (!video) {
        res.status(404).json({ error: 'Vídeo não encontrado.' });
        return;
      }
      // Adicionar na fila como prioridade
      await this.videoService.enqueueVideoNow(videoId, video.userEmail);
      res.status(200).json({ message: 'Vídeo colocado para processamento imediato.' });
    } catch (error: any) {
      this.logger.error('Erro ao processar vídeo imediatamente:', error);
      res.status(500).json({ error: error.message });
    }
  }

  /**
   * Cancela um vídeo (admin)
   */
  public async cancelVideo(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: 'Acesso restrito a administradores.' });
        return;
      }
      const { videoId } = req.params;
      if (!videoId) {
        res.status(400).json({ error: 'ID do vídeo é obrigatório.' });
        return;
      }
      // Buscar vídeo
      const video = await this.videoService.getVideoById(videoId);
      if (!video) {
        res.status(404).json({ error: 'Vídeo não encontrado.' });
        return;
      }
      // Cancelar vídeo
      await this.videoService.cancelVideo(videoId);
      res.status(200).json({ message: 'Vídeo cancelado com sucesso.' });
    } catch (error: any) {
      this.logger.error('Erro ao cancelar vídeo:', error);
      res.status(500).json({ error: error.message });
    }
  }

  /**
   * Retorna status da fila de transcrição com uso de recursos
   */
  public async getQueueStatus(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: 'Acesso restrito a administradores.' });
        return;
      }

      const queueStatus = this.transcriptionService.getQueueStatus();
      const processingSize = this.transcriptionService.getProcessingSize();
      
      res.status(200).json({
        success: true,
        queue: {
          queued: queueStatus.queued,
          processing: queueStatus.processing,
          totalCpuUsage: queueStatus.totalCpuUsage,
          totalMemoryUsage: queueStatus.totalMemoryUsage,
          resourceUsage: queueStatus.resourceUsage
        },
        limits: {
          maxConcurrentJobs: 2,
          maxCpuPerJob: 50, // 50% = 4 vCPUs de 8
          maxMemoryPerJob: 12 // 12GB de 32GB
        },
        server: {
          totalCpu: 8,
          totalMemory: 32
        }
      });
    } catch (error: any) {
      this.logger.error('Erro ao buscar status da fila:', error);
      res.status(500).json({ error: error.message });
    }
  }

  /**
   * Reenvia a transcrição já salva no banco para o Google Drive (apenas admin)
   */
  public async reuploadTranscription(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: 'Acesso restrito a administradores.' });
        return;
      }
      const { videoId } = req.params;
      if (!videoId) {
        res.status(400).json({ error: 'ID do vídeo é obrigatório.' });
        return;
      }
      // Buscar vídeo e transcrição
      const video = await this.videoService.getVideoById(videoId);
      if (!video) {
        res.status(404).json({ error: 'Vídeo não encontrado.' });
        return;
      }
      if (!video.transcrito || typeof video.transcrito !== 'string' || video.transcrito.trim().length === 0) {
        res.status(404).json({ error: 'Transcrição não encontrada para este vídeo.' });
        return;
      }
      const transcription = video.transcrito;
      const userEmail = video.userEmail;
      // Buscar tokens do usuário
      const { CollaboratorRepository } = require('../../data/repositories/collaborator-repository');
      const { TokenManager } = require('../../infrastructure/auth/token-manager');
      const { DriveService } = require('../../core/drive/drive-service');
      const { ConfigRepository } = require('../../data/repositories/config-repository');
      const logger = new Logger();
      const collaboratorRepository = new CollaboratorRepository(logger);
      const tokenManager = new TokenManager(collaboratorRepository, logger);
      const driveService = new DriveService(logger);
      // Buscar tokens atualizados
      await tokenManager.refreshTokenIfNeeded(userEmail);
      const tokens = await collaboratorRepository.getUserTokens(userEmail);
      if (!tokens || !tokens.accessToken) {
        res.status(400).json({ error: 'Tokens do usuário não encontrados ou inválidos.' });
        return;
      }
      const oauth2Client = tokenManager.createOAuth2Client(tokens.accessToken, tokens.refreshToken);
      const drive = require('googleapis').google.drive({ version: 'v3', auth: oauth2Client });
      // Buscar config de pasta personalizada
      let destinoFolderId = null;
      let transcriptionDocFileName = `${video.videoName} transcrição.doc`;
      let baseFileName = video.videoName;
      let googleDocsUrl = 'Link não disponível';
      let userId = video.usuarioId;
      let folderNameTranscricao = process.env.FOLDER_NAME_TRANSCRICAO || 'Transcrição';
      let rootFolderName = process.env.ROOT_FOLDER_NAME || 'Meet Recordings';
      let transcriptionConfig = null;
      if (userId) {
        const configRepo = new ConfigRepository(logger);
        transcriptionConfig = await configRepo.getTranscriptionConfig(userId);
      }
      if (transcriptionConfig && transcriptionConfig.transcriptionFolder) {
        const folderInput = transcriptionConfig.transcriptionFolder.trim();
        const linkMatch = folderInput.match(/folders\/([a-zA-Z0-9_-]+)/);
        if (linkMatch) {
          destinoFolderId = linkMatch[1];
        } else if (/^[a-zA-Z0-9_-]{10,}$/.test(folderInput)) {
          destinoFolderId = folderInput;
        } else {
          const rootFolderId = (await driveService.checkFolderHasCreated(rootFolderName, drive))?.folderId;
          if (rootFolderId) {
            const found = await driveService.checkFolderHasCreated(folderInput, drive, rootFolderId);
            if (found) destinoFolderId = found.folderId;
            else destinoFolderId = await driveService.createFolder(drive, folderInput, rootFolderId);
          }
        }
      }
      if (!destinoFolderId) {
        const rootFolderId = (await driveService.checkFolderHasCreated(rootFolderName, drive))?.folderId;
        const transFolder = await driveService.checkFolderHasCreated(folderNameTranscricao, drive, rootFolderId);
        destinoFolderId = transFolder ? transFolder.folderId : await driveService.createFolder(drive, folderNameTranscricao, rootFolderId);
      }
      // Upload do arquivo
      try {
        await driveService.uploadFile(
          drive,
          destinoFolderId,
          transcriptionDocFileName,
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          transcription
        );
      } catch (err: any) {
        if (err && err.message && err.message.toLowerCase().includes('invalid credentials')) {
          logger.warn('Credenciais inválidas detectadas ao reenviar arquivo, tentando renovar token...', { userEmail });
          await tokenManager.refreshTokenIfNeeded(userEmail);
          const refreshedTokens = await collaboratorRepository.getUserTokens(userEmail);
          const refreshedOauth2Client = tokenManager.createOAuth2Client(refreshedTokens?.accessToken || '', refreshedTokens?.refreshToken);
          const refreshedDrive = require('googleapis').google.drive({ version: 'v3', auth: refreshedOauth2Client });
          await driveService.uploadFile(
            refreshedDrive,
            destinoFolderId,
            transcriptionDocFileName,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            transcription
          );
        } else {
          throw err;
        }
      }
      // Buscar o documento criado para obter a URL
      try {
        const searchName = `${baseFileName} transcrição`;
        const found = await driveService.searchFilesByNamePart(
          drive,
          searchName,
          destinoFolderId
        );
        let foundDoc = null;
        if (found && found.length > 0) {
          foundDoc = found.find((f: any) => f.name.toLowerCase().includes(baseFileName.toLowerCase()) && f.name.toLowerCase().includes('transcrição'));
        }
        if (foundDoc) {
          googleDocsUrl = `https://drive.google.com/file/d/${foundDoc.id}/view`;
          if (foundDoc.mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
            googleDocsUrl = `https://docs.google.com/document/d/${foundDoc.id}/edit`;
          }
          // Atualizar link no banco
          await this.videoService.updateGoogleDocsUrl(String(videoId), String(googleDocsUrl));
        }
      } catch (urlError: any) {
        logger.warn('Não foi possível obter a URL do documento criado', {
          videoId,
          error: urlError && urlError.message ? urlError.message : String(urlError)
        });
      }
      res.status(200).json({
        success: true,
        message: 'Transcrição reenviada com sucesso para o Google Drive.',
        googleDocsUrl
      });
    } catch (error: any) {
      this.logger.error('Erro ao reenviar transcrição para o Drive:', error);
      res.status(500).json({ error: error.message });
    }
  }
}