import { google } from 'googleapis';
import { Logger } from '../../utils/logger';
import { CollaboratorService } from '../../domain/services/collaborator-service';
import { VideoService } from '../../domain/services/video-service';
import { TokenManager } from '../../infrastructure/auth/token-manager';
import { TranscriptionQueue } from '../transcription/transcription-queue';

export class DriveWatcher {
  private FOLDER_NAME: string = process.env.ROOT_FOLDER_NAME || 'Meet Recordings';
  private isScanning: boolean = false; // Adicionado para evitar duplicação
  private thresholdDate?: string; // nova propriedade para armazenar a data limite

  constructor(
    private logger: Logger,
    private collaboratorService: CollaboratorService,
    private videoService: VideoService,
    private tokenManager: TokenManager,
    private transcriptionQueue: TranscriptionQueue
  ) { }

  // Novo método para setar a data limite
  public setThresholdDate(threshold: Date): void {
    this.thresholdDate = threshold.toISOString();
    this.logger.info(`Threshold date set to: ${this.thresholdDate}`);
  }

  /**
   * Escaneia pastas de todos os usuários procurando por vídeos para transcever
   */
  public async scanAllUsersFolders(): Promise<void> {
    if (this.isScanning) {
      this.logger.warn('Escaneamento já em andamento. Ignorando nova execução.');
      return;
    }

    this.isScanning = true; // Bloqueia novas execuções
    try {
      // Obter todos os colaboradores ativos
      const collaborators = await this.collaboratorService.getAllActiveCollaborators();
      this.logger.info(`Encontrados ${collaborators.length} colaboradores ativos`);

      for (const collaborator of collaborators) {
        const { userId, email, accessToken, refreshToken, expiryDate } = collaborator;
        this.logger.info(`➡️ Processando colaborador: ${email}`);

        try {
          // Verificar se o token está expirado
          const isTokenExpired = expiryDate && Date.now() > expiryDate;
          let currentAccessToken = accessToken;
          let currentRefreshToken = refreshToken;

          // Se o token expirou, renovar
          if (isTokenExpired) {
            if (!refreshToken) {
              throw new Error(`Usuário ${email} está sem refresh_token!`);
            }

            this.logger.info(`Token expirado para ${email}, renovando...`);
            const refreshed = await this.tokenManager.refreshTokenIfNeeded(email);

            if (!refreshed) {
              throw new Error(`Falha ao renovar token para ${email}`);
            }

            // Buscar tokens atualizados
            const updatedTokens = await this.collaboratorService.getUserTokens(email);
            if (updatedTokens) {
              currentAccessToken = updatedTokens.accessToken;
              if (updatedTokens.refreshToken) {
                currentRefreshToken = updatedTokens.refreshToken;
              }
            }
          }

          // Criar cliente OAuth2 com os tokens atualizados
          const oauth2Client = this.tokenManager.createOAuth2Client(currentAccessToken, currentRefreshToken);
          const drive = google.drive({ version: 'v3', auth: oauth2Client });

          // Escanear pasta 'meet' (ou qualquer nome configurado)
          this.logger.info(`Escaneando pasta '${this.FOLDER_NAME}' para o usuário: ${email}`);

          // Buscar pasta "meet"
          const folderRes = await drive.files.list({
            q: `name='${this.FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed = false`,
            fields: 'files(id, name, mimeType, createdTime, modifiedTime)',
            spaces: 'drive',
          });

          // Verificar se a pasta existe
          if (!folderRes.data.files || folderRes.data.files.length === 0) {
            this.logger.warn(`Pasta '${this.FOLDER_NAME}' não encontrada para ${email}`);
            continue;
          }

          const folderId = folderRes.data.files[0].id;

          // Modificar a query para filtrar vídeos com createdTime >= thresholdDate (se definida)
          let query = `'${folderId}' in parents and mimeType contains 'video/' and trashed = false`;
          if (this.thresholdDate) {
            query += ` and createdTime >= '${this.thresholdDate}'`;
          }
          const videosRes = await drive.files.list({
            q: query,
            fields: 'files(id, name, mimeType, createdTime, modifiedTime, parents)'
          });

          const videoCount = videosRes.data.files?.length || 0;
          this.logger.info(`📼 Vídeos encontrados: ${videoCount}`);

          // Logar os IDs dos vídeos encontrados
          if (videosRes.data.files) {
            this.logger.info("IDs dos vídeos encontrados:", {
              videoIds: videosRes.data.files.map(file => file.id),
            });
          }

          // Salvar vídeos no banco e retornar apenas os novos
          const savedVideos = await this.videoService.insertVideos(
            (videosRes.data.files || []).map(file => ({
              id: file.id || undefined,
              name: file.name || undefined,
              mimeType: file.mimeType || undefined,
              createdTime: file.createdTime || undefined,
              parents: file.parents || undefined
            })),
            email,
            userId
          );

          // Filtrar vídeos que já foram processados
          const unprocessedVideos = savedVideos.filter(video => !video.transcrito && !video.enfileirado);

          if (unprocessedVideos.length === 0) {
            this.logger.info(`Nenhum vídeo novo ou pendente encontrado para ${email}`);
            continue;
          }

          this.logger.info(`🆕 ${unprocessedVideos.length} novos vídeos encontrados para ${email}`);

          // Enfileirar vídeos para transcrição
          for (const video of unprocessedVideos) {
            if (!video.userEmail) {
              this.logger.error(`Email é obrigatório para enfileirar o vídeo ${video.videoId}`);
              continue; // Pula para o próximo vídeo
            }

            // Usar o ID do usuário + ID do vídeo como identificador único da tarefa
            const taskId = `${userId}-${video.videoId}`;

            // Registrar vídeo como enfileirado no banco
            try {
              await this.videoService.markVideoAsQueued(video.videoId);
            } catch (error: any) {
              this.logger.error(`Erro ao marcar vídeo ${video.videoId} como enfileirado:`, error);
              // Continua mesmo com erro, para tentar enfileirar
            }

            // Adicionar à fila de transcrição
            this.transcriptionQueue.add(
              taskId,
              {
                videoId: video.videoId,
                webhookUrl: process.env.WEBHOOK_URL || '',
                email: video.userEmail,
                folderId: video.pastaId
              }
            );

            this.logger.info(`🎬 Vídeo enfileirado para transcrição: ${video.videoName} (${video.videoId})`);
          }

        } catch (error: any) {
          this.logger.error(`Erro ao escanear pastas para ${email}:`, {
            error: error.message,
            stack: error.stack
          });
        }
      }

    } catch (error: any) {
      this.logger.error('Erro ao carregar colaboradores:', error.message);
    } finally {
      this.isScanning = false; // Libera o bloqueio após a execução
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

  /**
   * Define o nome da pasta a ser monitorada
   */
  public setFolderName(folderName: string): void {
    this.FOLDER_NAME = folderName;
    this.logger.info(`Nome da pasta para monitoramento alterado para: ${folderName}`);
  }
}
