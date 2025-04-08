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

  constructor(
    private logger: Logger,
    private webhookService: WebhookService,
    private collaboratorRepository: CollaboratorRepository,
    private videoRepository: VideoRepository,
    private tokenManager: TokenManager,
    private driveService: DriveService,
    private audioProcessor: AudioProcessor,
    private transcriptionProcessor: TranscriptionProcessor
  ) {
    // Configurar caminhos do ffmpeg (podem vir de variáveis de ambiente)
    this.ffmpegPath = process.env.FFMPEG_PATH || "ffmpeg";
    this.ffprobePath = process.env.FFPROBE_PATH || "ffprobe";

    ffmpeg.setFfmpegPath(this.ffmpegPath);
    ffmpeg.setFfprobePath(this.ffprobePath);
  }
  // ... código anterior permanece inalterado ...

  public async processVideo(
    videoId: string,
    webhookUrl: string,
    userEmail: string,
    folderId?: string,
    taskId: string | null = null
  ): Promise<ProcessingResult> {
    videoId = String(videoId);
    const tempDir = path.join(process.cwd(), "temp");
    const videoFolderPath = path.join(tempDir, videoId);
    const videoPath = path.join(tempDir, `${videoId}.mp4`);
    const audioPath = path.join(tempDir, `${videoId}.mp3`);
    let transcriptionFilePath: string | null = null;
    let originalFolderPath: string | null = null;

    await fs.mkdir(videoFolderPath, { recursive: true });
    this.logger.info("Pasta do vídeo criada", { videoFolderPath });

    try {
      // Marcar o vídeo como em processamento
      await this.videoRepository.markVideoAsProcessing(videoId);

      // Verificar se o usuário existe e tem tokens
      const tokens = await this.collaboratorRepository.getUserTokens(userEmail);
      if (!tokens) {
        const errorMsg = `Tokens não encontrados para o usuário: ${userEmail}`;
        this.logger.error(errorMsg, { taskId, videoId });

        // Marcar o vídeo como tendo erro de autenticação
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

      await fs.mkdir(tempDir, { recursive: true });
      this.logger.info("Obtendo tokens do usuário", {
        userEmail,
        tokens: !!tokens,
      });
      if (!tokens || !tokens.accessToken) {
        throw new Error(`Tokens não encontrados para o usuário ${userEmail}`);
      }

      const oauth2Client = this.tokenManager.createOAuth2Client(
        tokens.accessToken,
        tokens.refreshToken
      );
      oauth2Client.on("tokens", async (updatedTokens) => {
        this.logger.info("Tokens atualizados automaticamente", { userEmail });
        const { access_token, refresh_token, expiry_date } = updatedTokens;
        await this.tokenManager.handleTokenUpdate(userEmail, tokens!, {
          access_token,
          refresh_token,
          expiry_date,
        } as any);
      });

      const drive = google.drive({ version: "v3", auth: oauth2Client });
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

      await this.driveService.downloadVideo(drive, videoId, videoPath);
      this.logger.info("Download do vídeo concluído", { videoId });

      // Converter para MP3
      this.logger.info("Iniciando conversão para MP3", { videoId });
      await this.audioProcessor.convertToMp3(videoPath, audioPath);
      this.logger.info("Conversão para MP3 concluída", { videoId });

      // Transcrever áudio
      this.logger.info("Iniciando transcrição", { videoId });
      let transcription: string;
      try {
        transcription = await this.transcriptionProcessor.transcribeAudio(
          audioPath,
          videoId
        );
        this.logger.info("Transcrição concluída", { videoId });
      } catch (transcriptionError: any) {
        this.logger.error(
          "Erro na transcrição, tentando abordagem alternativa",
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

      let transcriptionDocFileName: string;
      if (originalFolderPath) {
        const baseFileName = path.basename(
          originalFileName,
          path.extname(originalFileName)
        );
        transcriptionDocFileName = `${baseFileName}.doc`;

        this.logger.info(
          "Criando pasta no Google Drive para o vídeo e transcrição",
          {
            parentFolder: originalFolderPath,
            newFolderName: baseFileName,
          }
        );

        const driveFolderResponse = await drive.files.create({
          requestBody: {
            name: baseFileName,
            mimeType: "application/vnd.google-apps.folder",
            parents: [originalFolderPath],
          },
          fields: "id",
        });

        const newDriveFolderId = driveFolderResponse.data.id!;
        this.logger.info("Pasta criada no Google Drive", {
          folderId: newDriveFolderId,
        });

        this.logger.info("Movendo vídeo para a nova pasta no Google Drive", {
          videoId,
          newDriveFolderId,
          originalFolderPath,
        });

        const moved = await this.driveService.moveFile(
          drive,
          videoId,
          newDriveFolderId,
          originalFolderPath || ""
        );
        this.logger.info("Vídeo movido para a nova pasta no Google Drive", {
          videoId,
          newDriveFolderId,
        });

        await drive.files.update({
          fileId: videoId,
          addParents: newDriveFolderId,
          removeParents: originalFolderPath,
          fields: "id, parents",
        });
        this.logger.info("Vídeo movido para a nova pasta no Google Drive", {
          videoId,
          newDriveFolderId,
        });

        this.logger.info("Enviando transcrição (DOC) para o Google Drive", {
          folderId: newDriveFolderId,
          fileName: transcriptionDocFileName,
        });

        await drive.files.create({
          requestBody: {
            name: transcriptionDocFileName,
            parents: [newDriveFolderId],
            mimeType: "application/msword",
          },
          media: {
            mimeType: "application/msword",
            body: transcription,
          },
        });

        this.logger.info(
          "Transcrição (DOC) enviada para o Google Drive com sucesso"
        );
      }

      // Enviar notificação via webhook
      transcriptionDocFileName = `${videoId}.doc`;
      if (webhookUrl) {
        this.logger.info("Enviando notificação webhook com sucesso", {
          transcriptionDocFileName,
        });

        await this.webhookService.sendNotification(webhookUrl, {
          status: "success",
          transcription,
          videoId,
          docFileName: transcriptionDocFileName,
        });
      }

      // *** Ajuste aqui: usar videoId em vez de audioPath para a limpeza dos arquivos temporários ***
      await this.cleanupTempFiles(videoId);
      await this.videoRepository.markVideoAsCompleted(videoId);

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

      const isGoogleDriveFileError =
        error.message.includes("Arquivo vazio no Google Drive") ||
        error.message.includes("Arquivo sem conteúdo") ||
        error.message.includes("Resposta vazia do Google Drive") ||
        error.message.includes("Arquivo baixado está vazio") ||
        error.message.includes("Não foi possível obter metadados do arquivo");

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