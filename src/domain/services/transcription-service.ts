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

  public getQueueSize(): number {
    return this.transcriptionQueue.getQueueSize();
  }

  public getProcessingSize(): number {
    return this.transcriptionQueue.getProcessingSize();
  }
}