import { Logger } from "../../utils/logger";
import { VideoProcessor } from "./videoProcessor";

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
  ) {
    this.queue = new Map();
    this.processing = new Set();
    this.maxConcurrentJobs = parseInt("1", 10);

    this.logger.info(`Fila de transcrição inicializada com limite de ${this.maxConcurrentJobs} jobs simultâneos`);
  }

  public add(taskId: string, job: QueueJob): void {
    if (this.queue.has(taskId) || this.processing.has(taskId)) {
      this.logger.warn("Tarefa já existente na fila ou em processamento", { taskId });
      return;
    }
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
    if (!job) {
      this.logger.warn("Tarefa não encontrada na fila", { taskId });
      return;
    }

    const { videoId, webhookUrl, email, folderId } = job;
    this.processing.add(taskId);
    this.queue.delete(taskId);

    this.logger.info('Iniciando processamento do job', { taskId, videoId, email });

    try {
      await this.videoProcessor.processVideo(videoId, webhookUrl, email, folderId, taskId);
      this.logger.info('✅ Job finalizado com sucesso', { taskId, videoId });
    } catch (error: any) {
      this.logger.error('❌ Erro no job', { taskId, videoId, error: error.message });
    } finally {
      this.processing.delete(taskId);
      this._tryToProcess();
    }
  }
}
