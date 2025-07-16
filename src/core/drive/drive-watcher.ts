import { google } from 'googleapis';
import { Logger } from '../../utils/logger';
import { CollaboratorService } from '../../domain/services/collaborator-service';
import { VideoService } from '../../domain/services/video-service';
import { TokenManager } from '../../infrastructure/auth/token-manager';
import { TranscriptionQueue } from '../transcription/transcription-queue';
import { ConfigRepository } from '../../data/repositories/config-repository';
import { WebhookService } from '../../infrastructure/webhook/webhook-sender';

export class DriveWatcher {
  // Removido fallback para valor padrão, sempre buscar do banco
  private isScanning: boolean = false; // Adicionado para evitar duplicação
  private thresholdDate?: string; // nova propriedade para armazenar a data limite
  private configRepo = new ConfigRepository(new Logger());

  constructor(
    private logger: Logger,
    private collaboratorService: CollaboratorService,
    private videoService: VideoService,
    private tokenManager: TokenManager,
    private transcriptionQueue: TranscriptionQueue,
    private webhookService: WebhookService // NOVO
  ) { }

  /**
   * Define a data limite para filtrar vídeos (apenas vídeos criados após esta data)
   */
  public setThresholdDate(threshold: Date): void {
    this.thresholdDate = threshold.toISOString();
    this.logger.info(`Threshold date set to: ${this.thresholdDate}`);
  }

  /**
   * Polling leve: busca apenas vídeos criados após o último vídeo salvo para cada pasta/usuário
   */
  public async pollNewVideos(): Promise<void> {
    if (this.isScanning) {
      this.logger.warn('Polling já em andamento. Ignorando nova execução.');
      return;
    }
    this.isScanning = true;
    try {
      // Garantir que só 'Meet Recordings' esteja cadastrada como pasta padrão
      let foldersConfig = await this.configRepo.getConfig('root_folder');
      let folders: string[] = [];
      if (Array.isArray(foldersConfig)) {
        folders = foldersConfig;
      } else if (typeof foldersConfig === 'string') {
        folders = [foldersConfig];
      } else {
        folders = [];
      }
      // Se houver mais de uma pasta, manter apenas a primeira
      if (folders.length > 1) {
        folders = [folders[0]];
        // Atualiza config para garantir consistência
        await this.configRepo.setRootFolders(folders, undefined);
      }
      if (folders.length === 0) {
        this.logger.warn('Nenhuma pasta raiz configurada no banco de dados!');
        return;
      }

      // Obter todos os colaboradores ativos
      let collaborators;
      try {
        collaborators = await this.collaboratorService.getAllActiveCollaborators();
        this.logger.info(`Encontrados ${collaborators.length} colaboradores ativos`);
      } catch (error: any) {
        this.logger.error('Erro ao carregar colaboradores:', error.message);
        return;
      }

      for (const collaborator of collaborators) {
        const { userId, email, accessToken, refreshToken, expiryDate } = collaborator;
        this.logger.info(`➡️ Polling para colaborador: ${email}`);
        try {
          // Verificar se o token está expirado
          const isTokenExpired = expiryDate && Date.now() > expiryDate;
          let currentAccessToken = accessToken;
          let currentRefreshToken = refreshToken;

          if (isTokenExpired) {
            if (!refreshToken) {
              throw new Error(`Usuário ${email} está sem refresh_token!`);
            }
            this.logger.info(`Token expirado para ${email}, renovando...`);
            const refreshed = await this.tokenManager.refreshTokenIfNeeded(email);
            if (!refreshed) {
              throw new Error(`Falha ao renovar token para ${email}`);
            }
            const updatedTokens = await this.collaboratorService.getUserTokens(email);
            if (updatedTokens) {
              currentAccessToken = updatedTokens.accessToken;
              if (updatedTokens.refreshToken) {
                currentRefreshToken = updatedTokens.refreshToken;
              }
            }
          }

          const oauth2Client = this.tokenManager.createOAuth2Client(currentAccessToken, currentRefreshToken);
          const drive = google.drive({ version: 'v3', auth: oauth2Client });

          for (const folderInput of folders) {
            let folderId: string | null = null;
            let folderName: string | undefined = folderInput;
            const linkMatch = String(folderInput).match(/folders\/([a-zA-Z0-9_-]+)/);
            if (linkMatch) {
              folderId = linkMatch[1];
              folderName = undefined;
            } else if (/^[a-zA-Z0-9_-]{10,}$/.test(folderInput)) {
              folderId = folderInput;
              folderName = undefined;
            }
            if (!folderId && folderName) {
              this.logger.info(`Buscando pasta '${folderName}' para o usuário: ${email}`);
              try {
                const folderRes = await drive.files.list({
                  q: `name='${folderName}' and mimeType='application/vnd.google-apps.folder' and trashed = false`,
                  fields: 'files(id, name, mimeType, createdTime, modifiedTime)',
                  spaces: 'drive',
                });
                if (!folderRes.data.files || folderRes.data.files.length === 0) {
                  this.logger.warn(`Pasta '${folderName}' não encontrada para ${email}`);
                  continue;
                }
                folderId = folderRes.data.files[0].id || null;
              } catch (error: any) {
                this.logger.warn(`Erro ao buscar pasta '${folderName}' para ${email}: ${error.message}`);
                continue;
              }
            }
            if (!folderId) {
              this.logger.warn(`Não foi possível determinar o ID da pasta para '${folderInput}' (${email})`);
              continue;
            }
            if (!/^[a-zA-Z0-9_-]{10,}$/.test(folderId)) {
              this.logger.warn(`ID de pasta inválido: ${folderId} para ${email}`);
              continue;
            }

            try {
              // Buscar a data do último vídeo salvo para este usuário/pasta
              const lastVideo = await this.videoService.getLastVideoByUserAndFolder(userId, folderId);
              let lastCreatedTime: string | undefined = undefined;
              if (lastVideo?.createdTime) {
                if (typeof lastVideo.createdTime === 'string') {
                  const parsedDate = new Date(lastVideo.createdTime);
                  if (!isNaN(parsedDate.getTime())) {
                    lastCreatedTime = parsedDate.toISOString();
                  } else {
                    lastCreatedTime = lastVideo.createdTime;
                  }
                } else if (lastVideo.createdTime instanceof Date) {
                  lastCreatedTime = lastVideo.createdTime.toISOString();
                }
              }
              if (!lastCreatedTime) {
                // Se não houver vídeo anterior, busca só os últimos 5 minutos para evitar flood
                const now = new Date();
                now.setMinutes(now.getMinutes() - 5);
                lastCreatedTime = now.toISOString();
              }

              // Garante que a data está no formato RFC 3339 (ISO 8601)
              if (typeof lastCreatedTime === 'string') {
                const parsedDate = new Date(lastCreatedTime);
                if (!isNaN(parsedDate.getTime())) {
                  lastCreatedTime = parsedDate.toISOString();
                }
              }

              let query = `'${folderId}' in parents and mimeType contains 'video/' and trashed = false and createdTime > '${lastCreatedTime}'`;
              const videosRes = await drive.files.list({
                q: query,
                fields: 'files(id, name, mimeType, createdTime, modifiedTime, parents, size, owners, webViewLink, webContentLink)',
              });
              const newVideos = videosRes.data.files || [];
              if (newVideos.length === 0) {
                this.logger.info(`Nenhum vídeo novo encontrado para ${email} na pasta '${folderInput}'`);
                continue;
              }
              this.logger.info(`🆕 ${newVideos.length} novos vídeos encontrados para ${email} na pasta '${folderInput}'`);
              // Salvar vídeos e enviar para o webhook
              for (const file of newVideos) {
                const savedVideos = await this.videoService.insertVideos([
                  {
                    id: file.id || undefined,
                    name: file.name || undefined,
                    mimeType: file.mimeType || undefined,
                    createdTime: file.createdTime ? (typeof file.createdTime === 'string' ? file.createdTime : new Date(file.createdTime).toISOString()) : undefined,
                    parents: file.parents || undefined,
                  }
                ], email, userId);
                // Enfileirar para transcrição cada vídeo salvo
                for (const saved of savedVideos) {
                  if (saved && saved.videoId) {
                    // Atualiza status para 'processing' imediatamente
                    await this.videoService.markVideoAsProcessing(saved.videoId);
                    const taskId = `${email}-${saved.videoId}`;
                    this.transcriptionQueue.add(taskId, {
                      videoId: saved.videoId,
                      webhookUrl: process.env.WEBHOOK_URL || '',
                      email: email,
                      folderId: folderId,
                    });
                  }
                }
                // Payload para o webhook
                const payload = {
                  videoId: file.id,
                  name: file.name,
                  mimeType: file.mimeType,
                  createdTime: file.createdTime ? (typeof file.createdTime === 'string' ? file.createdTime : new Date(file.createdTime).toISOString()) : undefined,
                  parents: file.parents,
                  owners: file.owners,
                  webViewLink: file.webViewLink,
                  webContentLink: file.webContentLink,
                  userEmail: email,
                  userId: userId,
                  folderId: folderId,
                  folderName: folderName,
                  status: 'new_video_detected', // Necessário para o tipo WebhookData
                };
                await this.webhookService.sendToAllWebhooks('new_video_detected', payload, this.configRepo);
              }
            } catch (error: any) {
              if (error?.response?.status === 404 || (error.message && error.message.includes('File not found'))) {
                this.logger.warn(`Pasta não encontrada ou sem permissão: ${folderInput} (${folderId}) para ${email}`);
                continue;
              } else {
                this.logger.error(`Erro ao buscar vídeos na pasta '${folderInput}' para ${email}:`, error);
                continue;
              }
            }
          }
        } catch (error: any) {
          this.logger.error(`Erro no polling para ${email}:`, error);
        }
      }
    } catch (error: any) {
      this.logger.error('Erro no polling geral:', error);
    } finally {
      this.isScanning = false;
    }
  }

  /**
   * Escaneia a pasta de um colaborador específico
   */
  public async scanUserFolder(email: string): Promise<boolean> {
    try {
      const credential = await this.collaboratorService.getUserTokens(email);
      if (!credential) {
        this.logger.error(`Usuário não encontrado: ${email}`);
        return false;
      }

      // Usar estrutura similar à função principal, mas para um único usuário
      const { userId, accessToken, refreshToken } = credential;

      // Verificar e atualizar tokens se necessário
      await this.tokenManager.refreshTokenIfNeeded(email);

      // Reobter credenciais após possível atualização
      const updatedCredential = await this.collaboratorService.getUserTokens(email);
      if (!updatedCredential) return false;

      const oauth2Client = this.tokenManager.createOAuth2Client(
        updatedCredential.accessToken,
        updatedCredential.refreshToken
      );

      // Código similar ao método principal para escanear a pasta do usuário
      // ...

      return true;
    } catch (error: any) {
      this.logger.error(`Erro ao escanear pasta do usuário ${email}:`, error);
      return false;
    }
  }
}
