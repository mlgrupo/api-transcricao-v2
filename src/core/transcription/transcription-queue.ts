import { Logger } from "../../utils/logger";
import { VideoProcessor } from "./videoProcessor";
import { WebhookService } from "../../infrastructure/webhook/webhook-sender";
import { VideoRepository } from "../../data/repositories/video-repository";

interface QueueJob {
  videoId: string;
  webhookUrl: string;
  email: string;
  folderId?: string;
}

export class TranscriptionQueue {
  private queue: Map<string, QueueJob>;
  private processing: Set<string>;
  private maxConcurrentJobs: number;

  constructor(
    private logger: Logger,
    private videoProcessor: VideoProcessor,
    private webhookService: WebhookService,
    private videoRepository: VideoRepository
  ) {
    this.queue = new Map();
    this.processing = new Set();
    this.maxConcurrentJobs = parseInt("1", 10);
    
    this.logger.info(`Fila de transcrição inicializada com limite de ${this.maxConcurrentJobs} jobs simultâneos`);
  }

  public add(taskId: string, job: QueueJob): void {
    this.logger.info('Adicionando job à fila', { taskId, ...job });
    this.queue.set(taskId, job);
    this._tryToProcess();
  }

  public getQueueSize(): number {
    return this.queue.size;
  }

  public getProcessingSize(): number {
    return this.processing.size;
  }

  public getQueueStatus(): { queued: number; processing: number } {
    return {
      queued: this.queue.size,
      processing: this.processing.size
    };
  }

  private _tryToProcess(): void {
    if (this.processing.size >= this.maxConcurrentJobs) {
      this.logger.info('Limite de jobs paralelos atingido, aguardando...', {
        processing: this.processing.size,
        maxConcurrent: this.maxConcurrentJobs
      });
      return;
    }

    // Pegar primeiros jobs da fila que não estão em processamento
    const availableTasks = Array.from(this.queue.keys())
      .filter(id => !this.processing.has(id));
      
    for (const taskId of availableTasks) {
      if (this.processing.size >= this.maxConcurrentJobs) break;
      this._process(taskId);
    }
  }

  private async _process(taskId: string): Promise<void> {
    const job = this.queue.get(taskId);
    if (!job) return;
    
    const { videoId, webhookUrl, email, folderId } = job;
    this.processing.add(taskId);
    this.queue.delete(taskId);
    
    this.logger.info('Job iniciou processamento', { taskId, videoId, email });
    
    try {
      this.logger.info('Chamando processVideo com parâmetros:', { videoId, webhookUrl, email });
      
      // Processar o vídeo
      await this.videoProcessor.processVideo(videoId, webhookUrl, email, folderId, taskId);
      
      this.logger.info('✅ Job finalizado com sucesso', { taskId, videoId });
      
    } catch (error: any) {
      this.logger.error('❌ Erro no job:', {
        taskId, videoId, error: error.message, stack: error.stack
      });
      
      if (webhookUrl) {
        try {
          await this.webhookService.sendNotification(webhookUrl, {
            status: 'error',
            videoId,
            error: error.message
          });
        } catch (webhookError: any) {
          this.logger.error('Erro ao enviar notificação de webhook:', webhookError.message);
        }
      }
      
      try {
        await this.videoRepository.updateStatusVideo(videoId, false);
      } catch (err: any) {
        this.logger.error('Erro ao marcar status como falha:', err.message);
      }
    } finally {
      // Limpar arquivos temporários
      try {
        await this.videoProcessor.cleanupTempFiles(videoId);
      } catch (cleanupError: any) {
        this.logger.error('Erro ao limpar arquivos temporários:', {
          videoId,
          error: cleanupError.message
        });
      }
      
      this.processing.delete(taskId);
      this._tryToProcess();
    }
  }
}