import { Request, Response } from "express";
import { Logger } from "../../utils/logger";
import { TranscriptionService } from "../../domain/services/transcription-service";
import { VideoService } from "../../domain/services/video-service";

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
}