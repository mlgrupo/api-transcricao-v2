import { VideoRepository } from "../../data/repositories/video-repository";
import { Logger } from "../../utils/logger";
import { Video } from "../models/Video";
import { TranscriptionService } from "./transcription-service";

export class VideoService {
  private transcriptionService?: TranscriptionService;

  constructor(
    private videoRepository: VideoRepository,
    private logger: Logger,
    transcriptionService?: TranscriptionService
  ) {
    this.transcriptionService = transcriptionService;
  }

  public setTranscriptionService(service: TranscriptionService): void {
    this.transcriptionService = service;
  }

  public async saveVideo(videoData: {
    id: string;
    name: string;
    parentId?: string;
    createdTime?: Date;
    mimeType?: string;
    user_email: string;
    usuario_id?: string;
  }) {
    return this.videoRepository.saveVideo(videoData);
  }

  public async updateStatusVideo(videoId: string, status: boolean) {
    return this.videoRepository.updateStatusVideo(videoId, status);
  }

  public async getPendingVideos(limit: number = 5) {
    try {
      return await this.videoRepository.getPendingVideos(limit);
    } catch (error: any) {
      this.logger.error("Erro ao buscar vídeos pendentes:", error);
      throw error;
    }
  }

  public async markVideoAsQueued(videoId: string): Promise<Video> {
    try {
      return await this.videoRepository.markVideoAsQueued(videoId);
    } catch (error: any) {
      this.logger.error(`Erro ao marcar vídeo como enfileirado: ${videoId}`, error);
      throw error;
    }
  }

  public async resetQueueStatus(videoId: string): Promise<{ success: boolean; message: string }> {
    try {
      const video = await this.videoRepository.resetQueueStatus(videoId);
      this.logger.info(`Status de fila resetado para o vídeo: ${video.videoId}`);
      
      // Check if transcriptionService is defined before trying to use it
      if (this.transcriptionService) {
        // Re-enqueue the video for transcription
        const task = await this.transcriptionService.enqueueVideo({
          taskId: `retry-${video.videoId}`,
          videoId: video.videoId,
          webhookUrl: process.env.WEBHOOK_URL || '',
          email: video.userEmail!,
          folderId: video.pastaId
        });
        
        this.logger.info(`Vídeo ${video.videoId} re-enfileirado com sucesso, taskId: ${task}`);
      } else {
        this.logger.warn(`TranscriptionService não disponível, vídeo ${video.videoId} não foi re-enfileirado`);
      }
      
      return { 
        success: true, 
        message: `Status de fila resetado para o vídeo ${video.videoId}` 
      };
    } catch (error: any) {
      this.logger.error(`Erro ao resetar status de fila: ${videoId}`, error);
      throw error;
    }
  }

  public async markVideoAsCorrupted(videoId: string, errorMessage: string) {
    return this.videoRepository.markVideoAsCorrupted(videoId, errorMessage);
  }

  public async markVideoAsProcessing(videoId: string) {
    return this.videoRepository.markVideoAsProcessing(videoId);
  }

  public async insertVideos(
    videos: Array<{
      id?: string;
      name?: string;
      mimeType?: string;
      createdTime?: string;
      parents?: string[];
    }>,
    userEmail: string,
    userId?: string
  ): Promise<Video[]> {
    try {
      const savedVideos: Video[] = [];
      
      for (const video of videos) {
        if (!video.id || !video.name) continue;
        
        try {
          const videoData = {
            id: video.id,
            name: video.name,
            parentId: video.parents && video.parents.length > 0 ? video.parents[0] : null,
            mimeType: video.mimeType,
            createdTime: video.createdTime ? new Date(video.createdTime) : new Date(),
            user_email: userEmail,
            usuario_id: userId
          };
          
          const savedVideo = await this.videoRepository.saveVideo(videoData);
          if (savedVideo) savedVideos.push(savedVideo);
        } catch (err: any) {
          this.logger.error(`Erro ao salvar vídeo ${video.id}:`, err);
        }
      }
      
      return savedVideos;
    } catch (error: any) {
      this.logger.error("Erro ao inserir vídeos:", error);
      throw error;
    }
  }

  public async markVideoAsCompleted(videoId: string): Promise<Video> {
    try {
      return await this.videoRepository.markVideoAsCompleted(videoId);
    } catch (error: any) {
      this.logger.error(`Erro ao marcar vídeo como completo: ${videoId}`, error);
      throw error;
    }
  }

  public async getVideoById(videoId: string): Promise<Video | null> {
    try {
      return await this.videoRepository.getVideoById(videoId);
    } catch (error: any) {
      this.logger.error(`Erro ao buscar vídeo por ID: ${videoId}`, error);
      throw error;
    }
  }
}