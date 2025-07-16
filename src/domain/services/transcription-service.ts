import { Logger } from "../../utils/logger";
import { TranscriptionQueue } from "../../core/transcription/transcription-queue";

export interface TranscriptionJob {
  taskId: string;
  videoId: string;
  webhookUrl: string;
  email: string;
  folderId?: string;
}

export class TranscriptionService {
  constructor(
    private logger: Logger,
    private transcriptionQueue: TranscriptionQueue // Use a TranscriptionQueue
  ) {}

  public async enqueueVideo(job: TranscriptionJob): Promise<string> {
    const taskId = `${job.email}-${job.videoId}`;
    this.logger.info(`Adicionando job à fila: ${taskId}`);
    this.transcriptionQueue.add(taskId, job);
    return taskId;
  }

  public async enqueueVideoNow(job: TranscriptionJob): Promise<string> {
    const taskId = `${job.email}-${job.videoId}`;
    this.logger.info(`Adicionando job prioritário à fila: ${taskId}`);
    this.transcriptionQueue.addNow(taskId, job);
    return taskId;
  }

  public getQueueSize(): number {
    return this.transcriptionQueue.getQueueSize();
  }

  public getProcessingSize(): number {
    return this.transcriptionQueue.getProcessingSize();
  }

  public removeFromQueue(videoId: string): void {
    // Remove qualquer job da fila com esse videoId
    const keysToRemove = this.transcriptionQueue.getQueueKeys().filter(taskId => taskId.includes(videoId));
    for (const key of keysToRemove) {
      this.transcriptionQueue.removeByTaskId(key);
      this.logger.info(`Removido da fila: ${key}`);
    }
  }

  public cancelJob(videoId: string): void {
    this.transcriptionQueue.cancelJob(videoId);
  }
}