import { CronJob } from 'cron';
import { DriveWatcher } from '../../core/drive/drive-watcher';
import { VideoService } from '../../domain/services/video-service';
import { Logger } from '../../utils/logger';
import { TranscriptionQueue } from '../../core/transcription/transcription-queue';

export class JobScheduler {
  private isCheckingPendingVideos: boolean = false; // Adicionado para evitar duplicação

  constructor(
    private logger: Logger,
    private driveWatcher: DriveWatcher,
    private videoService: VideoService,
    private transcriptionQueue: TranscriptionQueue
  ) {}

  public setupJobs(): void {
    // Configurar jobs cron aqui
    this.setupDriveWatcherJob();
    this.setupPendingVideosJob();
  }

  private setupDriveWatcherJob(): void {
    // Escanear pastas a cada 1 minutos
    const scanJob = new CronJob(
      '*/1 * * * *',
      async () => {
        this.logger.info('Iniciando escaneamento periódico de pastas...');
        try {
          await this.driveWatcher.scanAllUsersFolders();
          this.logger.info('Escaneamento periódico de pastas concluído');
        } catch (error: any) {
          this.logger.error('Erro no escaneamento periódico:', error);
        }
      },
      null,
      true,
      'America/Sao_Paulo'
    );

    this.logger.info('Job de escaneamento de pastas configurado');
  }

  private setupPendingVideosJob(): void {
    // Verificar vídeos pendentes a cada 5 minutos
    const pendingVideosJob = new CronJob(
      '*/5 * * * *',
      async () => {
        if (this.isCheckingPendingVideos) {
          this.logger.warn('Verificação de vídeos pendentes já em andamento. Ignorando nova execução.');
          return;
        }

        this.isCheckingPendingVideos = true; // Bloqueia novas execuções
        this.logger.info('Executando verificação periódica de vídeos pendentes...');
        
        try {
          const pendingVideos = await this.videoService.getPendingVideos();
          
          this.logger.info(`Vídeos pendentes encontrados: ${pendingVideos.length}`, { 
            pendingVideos 
          });
          
          if (pendingVideos.length === 0) {
            this.logger.info('Nenhum vídeo pendente de transcrição encontrado.');
            return;
          }

          // Enfileirar vídeos pendentes
          for (const video of pendingVideos) {
            if (!video.userEmail) {
              this.logger.warn(`Vídeo ${video.videoId} sem email associado, não será enfileirado`);
              continue;
            }

            const taskId = `pending-${video.videoId}`;
            
            try {
              // Marcar vídeo como enfileirado para evitar duplicações
              await this.videoService.markVideoAsQueued(video.videoId);
              
              this.transcriptionQueue.add(
                taskId,
                {
                  videoId: video.videoId,
                  webhookUrl: process.env.WEBHOOK_URL || '',
                  email: video.userEmail,
                  folderId: video.pastaId
                }
              );
              
              this.logger.info(`Vídeo pendente enfileirado: ${video.videoId}`);
            } catch (error: any) {
              this.logger.error(`Erro ao enfileirar vídeo pendente ${video.videoId}:`, error);
            }
          }
        } catch (error: any) {
          this.logger.error('Erro na verificação periódica de vídeos pendentes:', error);
        } finally {
          this.isCheckingPendingVideos = false; // Libera o bloqueio após a execução
        }
      },
      null,
      true,
      'America/Sao_Paulo'
    );

    this.logger.info('Job de verificação de vídeos pendentes configurado');
  }
}

export const scheduleJobs = (
  logger: Logger,
  driveWatcher: DriveWatcher,
  videoService: VideoService,
  transcriptionQueue: TranscriptionQueue
): void => {
  const scheduler = new JobScheduler(
    logger, 
    driveWatcher, 
    videoService, 
    transcriptionQueue
  );
  
  scheduler.setupJobs();
};