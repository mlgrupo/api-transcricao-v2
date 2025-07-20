import { google } from "googleapis";
import fs from "fs/promises";
import path from "path";
import ffmpeg from "fluent-ffmpeg";
import { Logger } from "../../utils/logger";
import { WebhookService } from "../../infrastructure/webhook/webhook-sender";
import { CollaboratorRepository } from "../../data/repositories/collaborator-repository";
import { VideoRepository } from "../../data/repositories/video-repository";
import { TokenManager } from "../../infrastructure/auth/token-manager";
import { AudioProcessor } from "./audio-processor";
import { DriveService } from "../../core/drive/drive-service";
import type { TranscriptionProcessor } from "./transcription-processor";
import { ManagerFileAndFolder } from "../drive/ManagerFileAndFolder";
import { ConfigRepository } from '../../data/repositories/config-repository';

export interface ProcessingResult {
  success: boolean;
  transcription?: string;
  videoPath?: string;
  audioPath?: string;
  transcriptionFilePath?: string;
  originalFolderPath?: string;
  alreadyUploaded?: boolean;
  error?: string;
}

export class VideoProcessor {
  private ffmpegPath: string;
  private ffprobePath: string;
  private processingStartTime: Date;

  private folderNameGravacao: string = process.env.FOLDER_NAME_GRAVACAO || "Gravação";
  private folderNameTranscricao: string = process.env.FOLDER_NAME_TRANSCRICAO || 'Transcrição';
  private rootFolderName: string = process.env.ROOT_FOLDER_NAME || 'Meet Recordings';
  constructor(
    private logger: Logger,
    private webhookService: WebhookService,
    private collaboratorRepository: CollaboratorRepository,
    private videoRepository: VideoRepository,
    private tokenManager: TokenManager,
    private driveService: DriveService,
    private audioProcessor: AudioProcessor,
    private transcriptionProcessor: TranscriptionProcessor,
    private managerFileAndFolder: ManagerFileAndFolder
  ) {
    // Configurar caminhos do ffmpeg (podem vir de variáveis de ambiente)
    this.ffmpegPath = process.env.FFMPEG_PATH || "ffmpeg";
    this.ffprobePath = process.env.FFPROBE_PATH || "ffprobe";

    ffmpeg.setFfmpegPath(this.ffmpegPath);
    ffmpeg.setFfprobePath(this.ffprobePath);
  }

  public async processVideo(
    videoId: string,
    webhookUrl: string,
    userEmail: string,
    folderId?: string,
    taskId: string | null = null,
    cancelObj?: { cancelled: boolean }
  ): Promise<ProcessingResult> {
    videoId = String(videoId);
    const tempDir = path.join(process.cwd(), "temp");
    const videoFolderPath = path.join(tempDir, videoId);
    const videoPath = path.join(tempDir, `${videoId}.mp4`);
    const audioPath = path.join(tempDir, `${videoId}.mp3`);
    let originalFolderPath: string | null = null;

    await fs.mkdir(videoFolderPath, { recursive: true });
    this.logger.info("Pasta do vídeo criada", { videoFolderPath });

    try {
      // Inicializar tempo de processamento
      this.processingStartTime = new Date();
      
      // Marcar o vídeo como em processamento
      await this.videoRepository.markVideoAsProcessing(videoId);
      await this.videoRepository.updateProgress(videoId, 5, "Iniciando processamento");

      // Checar cancelamento
      if (cancelObj?.cancelled) throw new Error('Processamento cancelado pelo usuário');

      // Verificar se o usuário existe e tem tokens
      const tokens = await this.collaboratorRepository.getUserTokens(userEmail);
      if (!tokens) {
        const errorMsg = `Tokens não encontrados para o usuário: ${userEmail}`;
        this.logger.error(errorMsg, { taskId, videoId });
        await this.videoRepository.markVideoAsCorrupted(videoId, errorMsg);
        if (webhookUrl) {
          await this.webhookService.sendNotification(webhookUrl, {
            status: "error",
            videoId,
            error: errorMsg,
          });
        }
        return { success: false, error: errorMsg };
      }

      // Garantir que o token está válido e fazer refresh se necessário
      await this.tokenManager.refreshTokenIfNeeded(userEmail);
      const refreshedTokens = await this.collaboratorRepository.getUserTokens(userEmail);
      const finalTokens = refreshedTokens || tokens;

      await fs.mkdir(tempDir, { recursive: true });
      this.logger.info("Obtendo tokens do usuário", {
        userEmail,
        tokens: !!finalTokens,
      });
      if (!finalTokens || !finalTokens.accessToken) {
        throw new Error(`Tokens não encontrados para o usuário ${userEmail}`);
      }

      await this.videoRepository.updateProgress(videoId, 10, "Autenticação verificada");

      // Checar cancelamento
      if (cancelObj?.cancelled) throw new Error('Processamento cancelado pelo usuário');

      const oauth2Client = this.tokenManager.createOAuth2Client(
        finalTokens.accessToken,
        finalTokens.refreshToken
      );
      oauth2Client.on("tokens", async (updatedTokens) => {
        this.logger.info("Tokens atualizados automaticamente", { userEmail });
        const { access_token, refresh_token, expiry_date } = updatedTokens;
        await this.tokenManager.handleTokenUpdate(userEmail, finalTokens!, {
          access_token,
          refresh_token,
          expiry_date,
        } as any);
      });

      const drive = google.drive({ version: "v3", auth: oauth2Client });
    
      // pegando o dados do vídeo
      const fileInfo = await drive.files.get({
        fileId: videoId,
        fields: "name,parents",
      });

      const originalFileName = fileInfo.data.name!;
      const fileParents = fileInfo.data.parents || [];
      originalFolderPath =
        folderId || (fileParents.length > 0 ? fileParents[0] : null);

      this.logger.info("Iniciando download do vídeo", {
        videoId,
        fileName: originalFileName,
        folderId: originalFolderPath,
      });

      await this.videoRepository.updateProgress(videoId, 15, "Iniciando download do vídeo");
      // Checar cancelamento antes do download
      if (cancelObj?.cancelled) throw new Error('Processamento cancelado pelo usuário');
      await this.driveService.downloadVideo(drive, videoId, videoPath, cancelObj);
      // Checar cancelamento após download
      if (cancelObj?.cancelled) throw new Error('Processamento cancelado pelo usuário');
      this.logger.info("Download do vídeo concluído", { videoId });
      await this.videoRepository.updateProgress(videoId, 25, "Download concluído");

      // Download do vídeo já foi feito em videoPath
      // Não precisa mais converter para MP3
      // Transcrever vídeo diretamente
      this.logger.info("Iniciando transcrição", { videoId });
      let transcription: string;
      try {
        await this.videoRepository.updateProgress(videoId, 55, "Iniciando transcrição do vídeo");
        if (cancelObj?.cancelled) throw new Error('Processamento cancelado pelo usuário');
        transcription = await this.transcriptionProcessor.transcribeAudio(
          videoPath, // agora passa o caminho do vídeo
          videoId
        );
        this.logger.info("Transcrição concluída", { videoId });
        await this.videoRepository.updateProgress(videoId, 75, "Transcrição concluída");
      } catch (transcriptionError: any) {
        this.logger.error(
          "Erro na transcrição",
          {
            videoId,
            error: transcriptionError.message,
          }
        );
        transcription =
          "Não foi possível transcrever este vídeo automaticamente. Por favor, revise manualmente o conteúdo.";
      }

      await this.logger.info(
        `✅ Transcrição concluída para o vídeo ${videoId}`,
        {
          videoId,
          userEmail,
          transcription,
        }
      );

      // Salvar a transcrição no banco
      // Se a transcrição for erro técnico, não salvar, marcar como erro e notificar
      if (transcription && transcription.trim().startsWith('Este vídeo não pôde ser transcrito devido a um erro técnico') ||
          transcription && transcription.trim().startsWith('Não foi possível transcrever este vídeo automaticamente.')) {
        await this.videoRepository.updateProgress(videoId, 0, 'Erro técnico na transcrição');
        await this.videoRepository.markVideoAsCorrupted(videoId, transcription);
        this.logger.error('Erro técnico na transcrição, não será criado arquivo nem salvo texto.', { videoId, error: transcription });
        // Enviar webhook de erro
        if (webhookUrl) {
          await this.webhookService.sendNotification(webhookUrl, {
            status: 'error',
            videoId,
            error: transcription,
          });
        }
        const configRepo = new ConfigRepository(this.logger);
        await this.webhookService.sendToAllWebhooks('transcription_failed', {
          videoId,
          userEmail,
          error: transcription,
          status: 'transcription_failed',
        }, configRepo);
        await this.cleanupTempFiles(videoId);
        return { success: false, error: transcription };
      } else {
        await this.videoRepository.updateTranscriptionText(videoId, transcription);
      }

      // Buscar configuração de movimentação do usuário
      const collaborator = await this.collaboratorRepository.getCollaboratorByEmail(userEmail);
      let userId = collaborator?.userId;
      let transcriptionConfig = null;
      if (userId) {
        const configRepo = new ConfigRepository(this.logger);
        transcriptionConfig = await configRepo.getTranscriptionConfig(userId);
      }

      let transcriptionDocFileName;
      let googleDocsUrl = 'Link não disponível'; // Declarar fora do if para estar disponível no webhook
      
      if (originalFolderPath) {
        // Extrair o nome base do arquivo corretamente
        const fileExtension = originalFileName.toLowerCase().endsWith('.mp4') ? '.mp4' : '';
        const baseFileName = fileExtension
          ? originalFileName.slice(0, -fileExtension.length)
          : originalFileName;
        transcriptionDocFileName = `${baseFileName} transcrição.doc`;

        // --- NOVA LÓGICA DE PASTA DE DESTINO ---
        let destinoFolderId = null;
        let destinoFolderName = null;
        // Se houver configuração personalizada, buscar/criar a pasta
        if (transcriptionConfig && transcriptionConfig.transcriptionFolder) {
          const folderInput = transcriptionConfig.transcriptionFolder.trim();
          // Se for link do Google Drive
          const linkMatch = folderInput.match(/folders\/([a-zA-Z0-9_-]+)/);
          if (linkMatch) {
            destinoFolderId = linkMatch[1];
          } else if (/^[a-zA-Z0-9_-]{10,}$/.test(folderInput)) {
            destinoFolderId = folderInput;
          } else {
            // Buscar por nome
            const rootFolderId = (await this.driveService.checkFolderHasCreated(this.rootFolderName, drive))?.folderId;
            if (rootFolderId) {
              const found = await this.driveService.checkFolderHasCreated(folderInput, drive, rootFolderId);
              if (found) destinoFolderId = found.folderId;
              else destinoFolderId = await this.driveService.createFolder(drive, folderInput, rootFolderId);
            }
          }
        }
        // Se não achou destinoFolderId, usar pasta padrão "Transcrição"
        if (!destinoFolderId) {
          const rootFolderId = (await this.driveService.checkFolderHasCreated(this.rootFolderName, drive))?.folderId;
          const transFolder = await this.driveService.checkFolderHasCreated(this.folderNameTranscricao, drive, rootFolderId);
          destinoFolderId = transFolder ? transFolder.folderId : await this.driveService.createFolder(drive, this.folderNameTranscricao, rootFolderId);
        }

        await this.videoRepository.updateProgress(videoId, 80, "Criando documento de transcrição");

        // Enviar transcrição para a pasta de destino
        this.logger.info("Enviando transcrição (DOC) para pasta de transcrição personalizada", {
          folderId: destinoFolderId,
          fileName: transcriptionDocFileName,
        });
        // Salvar arquivo na pasta correta
        await this.driveService.uploadFile(
          drive,
          destinoFolderId,
          transcriptionDocFileName,
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          transcription
        );

        // Buscar o documento criado para obter a URL
        try {
          const searchName = `${baseFileName} transcrição`;
          const found = await this.driveService.searchFilesByNamePart(
            drive,
            searchName,
            destinoFolderId
          );
          let foundDoc = null;
          if (found && found.length > 0) {
            foundDoc = found.find(f => f.name.toLowerCase().includes(baseFileName.toLowerCase()) && f.name.toLowerCase().includes('transcrição'));
          }
          if (foundDoc) {
            googleDocsUrl = `https://drive.google.com/file/d/${foundDoc.id}/view`;
            if (foundDoc.mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
              googleDocsUrl = `https://docs.google.com/document/d/${foundDoc.id}/edit`;
            }
            await this.videoRepository.updateGoogleDocsUrl(String(videoId), String(googleDocsUrl));
            this.logger.info("URL do documento salva no banco de dados", {
              videoId,
              docId: foundDoc.id,
              googleDocsUrl
            });
          }
        } catch (urlError: any) {
          this.logger.warn("Não foi possível obter a URL do documento criado", {
            videoId,
            error: urlError && urlError.message ? urlError.message : String(urlError)
          });
        }
      }

      // Após salvar a transcrição, mover o vídeo se configurado
      if (transcriptionConfig && transcriptionConfig.moveVideoAfterTranscription && transcriptionConfig.videoDestinationFolder) {
        let destinoVideoFolderId = null;
        const folderInput = transcriptionConfig.videoDestinationFolder.trim();
        // Se for link do Google Drive
        const linkMatch = folderInput.match(/folders\/([a-zA-Z0-9_-]+)/);
        if (linkMatch) {
          destinoVideoFolderId = linkMatch[1];
        } else if (/^[a-zA-Z0-9_-]{10,}$/.test(folderInput)) {
          destinoVideoFolderId = folderInput;
        } else {
          // Buscar por nome
          const rootFolderId = (await this.driveService.checkFolderHasCreated(this.rootFolderName, drive))?.folderId;
          if (rootFolderId) {
            const found = await this.driveService.checkFolderHasCreated(folderInput, drive, rootFolderId);
            if (found) destinoVideoFolderId = found.folderId;
            else destinoVideoFolderId = await this.driveService.createFolder(drive, folderInput, rootFolderId);
          }
        }
        if (destinoVideoFolderId) {
          // Buscar pasta atual do vídeo
          const fileInfo = await drive.files.get({ fileId: videoId, fields: 'parents' });
          const oldParent = fileInfo.data.parents && fileInfo.data.parents[0];
          if (oldParent && oldParent !== destinoVideoFolderId) {
            await drive.files.update({ fileId: videoId, addParents: destinoVideoFolderId, removeParents: oldParent });
            this.logger.info('Vídeo movido para pasta de destino configurada', { videoId, destinoVideoFolderId });
          } else {
            this.logger.info('Vídeo já está na pasta de destino ou não foi possível determinar pasta atual', { videoId, destinoVideoFolderId });
          }
        } else {
          this.logger.warn('Não foi possível determinar a pasta de destino para mover o vídeo', { videoId, folderInput });
        }
      } else {
        this.logger.info('Movimentação de vídeo não configurada ou não habilitada, vídeo permanecerá na pasta original', { videoId });
      }

      await this.videoRepository.updateProgress(videoId, 90, "Enviando notificações");

      // Enviar notificação via webhook
      if (webhookUrl) {
        this.logger.info("Enviando notificação webhook com sucesso", {
          transcriptionDocFileName,
        });

        await this.webhookService.sendNotification(webhookUrl, {
          status: "success",
          transcription,
          videoId,
          userEmail,
          docFileName: transcriptionDocFileName,
        });
      }

      // Enviar webhook de transcrição concluída
      if (transcription && transcription.trim() && !transcription.trim().startsWith('Não foi possível transcrever este vídeo automaticamente.') && !transcription.trim().startsWith('Este vídeo não pôde ser transcrito devido a um erro técnico')) {
        const configRepo = new ConfigRepository(this.logger);
        
        // Buscar informações do vídeo no banco
        const videoInfo = await this.videoRepository.getVideoById(videoId);
        
        // Construir links - usar URL já obtida ou buscar do banco
        const videoLink = `https://drive.google.com/file/d/${videoId}/view`;
        const transcriptionLink = googleDocsUrl !== 'Link não disponível' ? googleDocsUrl : (videoInfo?.googleDocsUrl || 'Link não disponível');
        const videoName = videoInfo?.videoName || 'Vídeo sem nome';
        
        // Calcular tempo de processamento
        const processingEndTime = new Date();
        const processingDuration = processingEndTime.getTime() - this.processingStartTime.getTime();
        const processingDurationSeconds = Math.round(processingDuration / 1000);
        const processingDurationMinutes = Math.round(processingDurationSeconds / 60);
        
        // Formatar duração do vídeo (se disponível)
        let videoDuration = 'Não disponível';
        let videoDurationSeconds = 0;
        try {
          if (videoPath) {
            const ffprobe = require('fluent-ffmpeg');
            const getVideoDuration = () => {
              return new Promise((resolve, reject) => {
                ffprobe.ffprobe(videoPath, (err: any, metadata: any) => {
                  if (err) {
                    reject(err);
                  } else {
                    resolve(metadata.format.duration);
                  }
                });
              });
            };
            videoDurationSeconds = await getVideoDuration() as number;
            const hours = Math.floor(videoDurationSeconds / 3600);
            const minutes = Math.floor((videoDurationSeconds % 3600) / 60);
            const seconds = Math.floor(videoDurationSeconds % 60);
            videoDuration = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
          }
        } catch (durationError) {
          this.logger.warn('Não foi possível obter duração do vídeo', { videoId, error: durationError });
        }
        
        await this.webhookService.sendToAllWebhooks('transcription_completed', {
          videoId,
          userEmail,
          videoName,
          transcription,
          docFileName: transcriptionDocFileName,
          status: 'transcription_completed',
          links: {
            video: videoLink,
            transcription: transcriptionLink
          },
          timing: {
            videoDuration: videoDuration,
            videoDurationSeconds: videoDurationSeconds,
            processingDurationSeconds: processingDurationSeconds,
            processingDurationMinutes: processingDurationMinutes,
            processingStartTime: this.processingStartTime.toISOString(),
            processingEndTime: processingEndTime.toISOString()
          },
          timestamp: new Date().toISOString()
        }, configRepo);
      }

      // *** Ajuste aqui: usar videoId em vez de audioPath para a limpeza dos arquivos temporários ***
      await this.cleanupTempFiles(videoId);
      await this.videoRepository.updateProgress(videoId, 100, "Processamento concluído");

      return {
        success: true,
        transcription,
      };
    } catch (error: any) {
      this.logger.error("Erro no processamento do vídeo:", {
        error: error.message,
        stack: error.stack,
        taskId,
        videoId,
        email: userEmail,
        folderId,
      });

      await this.videoRepository.updateProgress(videoId, 0, `Erro: ${error.message}`);

      const isGoogleDriveFileError =
        error.message.includes("Arquivo vazio no Google Drive") ||
        error.message.includes("Arquivo sem conteúdo") ||
        error.message.includes("Resposta vazia do Google Drive") ||
        error.message.includes("Arquivo baixado está vazio") ||
        error.message.includes("Não foi possível obter metadados do arquivo");

      // NOVO: Detectar erro de credenciais inválidas do Google Drive
      const isInvalidCredentials = error.message && error.message.toLowerCase().includes("invalid credentials");
      if (isInvalidCredentials) {
        const reconectarMsg = "Credenciais do Google Drive inválidas. Por favor, reconecte sua conta do Google Drive no painel de administração.";
        this.logger.error("Usuário precisa reconectar o Google Drive!", { videoId, userEmail });
        await this.videoRepository.markVideoAsCorrupted(videoId, reconectarMsg);
        if (webhookUrl) {
          await this.webhookService.sendNotification(webhookUrl, {
            status: "error",
            videoId,
            error: reconectarMsg,
            action: "reconnect_drive"
          });
        }
        const configRepo = new ConfigRepository(this.logger);
        
        // Buscar informações do vídeo no banco
        const videoInfo = await this.videoRepository.getVideoById(videoId);
        
        // Construir links
        const videoLink = `https://drive.google.com/file/d/${videoId}/view`;
        const videoName = videoInfo?.videoName || 'Vídeo sem nome';
        
        await this.webhookService.sendToAllWebhooks('transcription_failed', {
          videoId,
          userEmail,
          videoName,
          error: reconectarMsg,
          status: 'transcription_failed',
          action: 'reconnect_drive',
          links: {
            video: videoLink
          },
          timestamp: new Date().toISOString()
        }, configRepo);
        try {
          this.logger.info("Limpando arquivos temporários após erro...", {
            videoId,
          });
          return {
            success: false,
            error: reconectarMsg,
            videoPath,
            audioPath,
            alreadyUploaded: true,
          };
        } catch (cleanupError: any) {
          this.logger.error("Erro ao limpar arquivos temporários:", {
            error: cleanupError,
            videoId,
          });
          this.webhookService.sendNotification(webhookUrl, {
            status: "error",
            videoId,
            error: cleanupError.message,
            message:
              "Erro ao limpar arquivos temporários, cuidado com o acumulo de pastas",
          });
        } finally {
          await this.cleanupTempFiles(videoId);
        }
        return { success: false, error: reconectarMsg };
      }

      if (isGoogleDriveFileError) {
        this.logger.info("Marcando vídeo como corrompido no banco de dados", {
          videoId,
          error: error.message,
        });

        await this.videoRepository.markVideoAsCorrupted(videoId, error.message);
      }

      if (webhookUrl) {
        await this.webhookService.sendNotification(webhookUrl, {
          status: "error",
          videoId,
          error: error.message,
        });
      }

      // Enviar webhook de erro na transcrição
      const configRepo = new ConfigRepository(this.logger);
      
      // Buscar informações do vídeo no banco
      const videoInfo = await this.videoRepository.getVideoById(videoId);
      
      // Construir links
      const videoLink = `https://drive.google.com/file/d/${videoId}/view`;
      const videoName = videoInfo?.videoName || 'Vídeo sem nome';
      
      await this.webhookService.sendToAllWebhooks('transcription_failed', {
        videoId,
        userEmail,
        videoName,
        error: error.message,
        status: 'transcription_failed',
        links: {
          video: videoLink
        },
        timestamp: new Date().toISOString()
      }, configRepo);

      try {
        this.logger.info("Limpando arquivos temporários após erro...", {
          videoId,
        });
        // Aqui permanece videoId, que é o identificador correto para cleanup
        return {
          success: false,
          error: error.message,
          videoPath,
          audioPath,
          alreadyUploaded: true,
        };
      } catch (cleanupError: any) {
        this.logger.error("Erro ao limpar arquivos temporários:", {
          error: cleanupError,
          videoId,
        });
        this.webhookService.sendNotification(webhookUrl, {
          status: "error",
          videoId,
          error: cleanupError.message,
          message:
            "Erro ao limpar arquivos temporários, cuidado com o acumulo de pastas",
        });
      } finally {
        await this.cleanupTempFiles(videoId);
      }
      return { success: false, error: error.message };
    }
  }

  public async cleanupTempFiles(identifier: string): Promise<void> {
    if (!identifier) return;

    const tempDir = path.join(process.cwd(), "temp");
    const videoFolderPath = path.join(tempDir, identifier);
    const videoPath = path.join(tempDir, `${identifier}.mp4`);
    const audioPath = path.join(tempDir, `${identifier}.mp3`);
    const possibleDocPath = path.join(tempDir, `${identifier}.doc`);

    this.logger.info("Limpando arquivos temporários", { identifier });

    const filesToRemove = [videoPath, audioPath, possibleDocPath];
    for (const file of filesToRemove) {
      try {
        const exists = await fs
          .access(file)
          .then(() => true)
          .catch(() => false);
        if (exists) {
          await fs.unlink(file);
          this.logger.info("Arquivo temporário removido", { file });
        }
      } catch (err: any) {
        this.logger.warn("Não foi possível remover arquivo temporário", {
          file,
          error: err.message,
        });
      }
    }

    try {
      const exists = await fs
        .access(videoFolderPath)
        .then(() => true)
        .catch(() => false);
      if (exists) {
        await fs.rm(videoFolderPath, { recursive: true, force: true });
        this.logger.info("Pasta temporária removida", {
          folder: videoFolderPath,
        });
      }
    } catch (err: any) {
      this.logger.warn("Não foi possível remover pasta temporária", {
        folder: videoFolderPath,
        error: err.message,
      });
    }
  }
}