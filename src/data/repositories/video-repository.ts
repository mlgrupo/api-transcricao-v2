import { Repository } from "typeorm";
import { AppDataSource } from "../data-source";
import { Video } from "../../domain/models/Video";
import { Logger } from "../../utils/logger";
import { promisify } from "util";
import { exec } from "child_process";
import * as path from "path";
import * as fs from "fs/promises";

export class VideoRepository {
  private repository: Repository<Video>;
  private logger: Logger;

  constructor(logger: Logger) {
    this.repository = AppDataSource.getRepository(Video);
    this.logger = logger;
  }

  public async saveVideo(videoData: {
    id: string;
    name: string;
    parentId?: string | null;
    createdTime?: Date;
    mimeType?: string;
    user_email: string;
    usuario_id?: string;
  }): Promise<Video | null> {
    try {
      // Verificar se o vídeo já existe
      const existingVideo = await this.getVideoById(videoData.id);
      if (existingVideo) {
        this.logger.info(`⚠️ Vídeo já existente, ignorado pelo banco: ${videoData.id}`);
        return null;
      }

      const video = new Video();
      video.videoId = videoData.id;
      video.videoName = videoData.name;
      video.pastaId = videoData.parentId || undefined;
      video.createdTime = videoData.createdTime;
      video.mimeType = videoData.mimeType;
      video.userEmail = videoData.user_email;
      video.usuarioId = videoData.usuario_id;
      video.transcrito = undefined;
      video.enfileirado = false;

      const savedVideo = await this.repository.save(video);
      this.logger.info(`✅ Vídeo salvo com sucesso: ${savedVideo.videoId}`);
      return savedVideo;
    } catch (error: any) {
      this.logger.error("❌ Erro ao salvar vídeo:", error);
      throw error;
    }
  }

  public async getVideoById(videoId: string): Promise<Video | null> {
    try {
      return await this.repository.findOne({
        where: { videoId }
      });
    } catch (error: any) {
      this.logger.error("Erro ao buscar vídeo por ID:", error);
      throw error;
    }
  }

  public async updateStatusVideo(videoId: string, status: string | undefined): Promise<boolean> {
    try {
      const result = await this.repository.update(
        { videoId },
        { transcrito: status }
      );
      return result.affected !== undefined && result.affected > 0;
    } catch (error: any) {
      this.logger.error("Erro ao atualizar o status do vídeo:", error);
      throw error;
    }
  }

  public async updateVideoStatus(videoId: string, status: string): Promise<void> {
    await this.repository.createQueryBuilder()
      .update(Video)
      .set({ status, enfileirado: false, dtAtualizacao: new Date() })
      .where("videoId = :videoId", { videoId })
      .execute();
  }

  public async getPendingVideos(limit: number = 5): Promise<Video[]> {
    try {
      return await this.repository.createQueryBuilder("video")
        .where("(video.transcrito IS NULL OR video.transcrito = '')")
        .andWhere("video.enfileirado = :enfileirado", { enfileirado: false })
        .andWhere("(video.status IS NULL OR (video.status != :processing AND video.status != :completed AND video.status != :error AND video.status != :cancelled))", { 
          processing: "processing", 
          completed: "completed", 
          error: "error",
          cancelled: "cancelled"
        })
        .orderBy("video.dtCriacao", "ASC")
        .limit(limit)
        .getMany();
    } catch (error: any) {
      this.logger.error("Erro ao buscar vídeos pendentes:", error);
      throw error;
    }
  }
  public async markVideoAsQueued(videoId: string): Promise<Video> {
    try {
      const result = await this.repository.createQueryBuilder()
        .update(Video)
        .set({ enfileirado: true })
        .where("videoId = :videoId", { videoId })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado ou já marcado`);
      }
      
      return result.raw[0];
    } catch (error: any) {
      this.logger.error(`Erro ao marcar vídeo como enfileirado: ${videoId}`, error);
      throw error;
    }
  }
  public async resetQueueStatus(videoId: string): Promise<Video> {
    try {
      const result = await this.repository.update(
        { videoId },
        { enfileirado: false }
      );
      const getVideoById = await this.getVideoById(videoId);
      
      if(!getVideoById) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado`);
      }
      return getVideoById;
    } catch (error: any) {
      this.logger.error(`Erro ao resetar status de fila: ${videoId}`, error);
      throw error;
    }
  }

  public async markVideoAsCorrupted(videoId: string, errorMessage: string): Promise<Video> {
    try {
      const result = await this.repository.createQueryBuilder()
        .update(Video)
        .set({ 
          transcrito: 'ERRO',
          enfileirado: false,
          status: "error",
          errorMessage,
          dtAtualizacao: new Date()
        })
        .where("videoId = :videoId", { videoId })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado`);
      }
      
      return result.raw[0];
    } catch (error: any) {
      this.logger.error(`Erro ao marcar vídeo como corrompido: ${videoId}`, error);
      throw error;
    }
  }

  public async markVideoAsProcessing(videoId: string): Promise<Video> {
    try {
      const result = await this.repository.createQueryBuilder()
        .update(Video)
        .set({ 
          enfileirado: true,
          status: "processing",
          dtAtualizacao: new Date()
        })
        .where("videoId = :videoId", { videoId })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado`);
      }
      
      return result.raw[0];
    } catch (error: any) {
      this.logger.error(`Erro ao marcar vídeo como em processamento: ${videoId}`, error);
      throw error;
    }
  }

  public async markVideoAsCompleted(videoId: string): Promise<Video> {
    try {
      const result = await this.repository.createQueryBuilder()
        .update(Video)
        .set({ 
          transcrito: undefined,
          enfileirado: false,
          status: "completed",
          dtAtualizacao: new Date()
        })
        .where("videoId = :videoId", { videoId })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado`);
      }
      
      return result.raw[0];
    } catch (error: any) {
      this.logger.error(`Erro ao marcar vídeo como completo: ${videoId}`, error);
      throw error;
    }
  }

  public async updateProgress(videoId: string, progress: number, etapaAtual: string): Promise<Video> {
    try {
      const result = await this.repository.createQueryBuilder()
        .update(Video)
        .set({ 
          progress,
          etapaAtual,
          dtAtualizacao: new Date()
        })
        .where("videoId = :videoId", { videoId })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado`);
      }
      
      this.logger.info(`Progresso atualizado para vídeo ${videoId}: ${progress}% - ${etapaAtual}`);
      return result.raw[0];
    } catch (error: any) {
      this.logger.error(`Erro ao atualizar progresso do vídeo: ${videoId}`, error);
      throw error;
    }
  }

  public async updateGoogleDocsUrl(videoId: string, googleDocsUrl: string): Promise<Video> {
    try {
      const result = await this.repository.createQueryBuilder()
        .update(Video)
        .set({ 
          googleDocsUrl,
          dtAtualizacao: new Date()
        })
        .where("videoId = :videoId", { videoId })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado`);
      }
      
      this.logger.info(`URL do documento atualizada para vídeo ${videoId}: ${googleDocsUrl}`);
      return result.raw[0];
    } catch (error: any) {
      this.logger.error(`Erro ao atualizar URL do documento do vídeo: ${videoId}`, error);
      throw error;
    }
  }

  /**
   * Atualiza o texto da transcrição do vídeo
   */
  public async updateTranscriptionText(videoId: string, transcription: string): Promise<Video> {
    try {
      const result = await this.repository.createQueryBuilder()
        .update(Video)
        .set({ 
          transcrito: transcription || undefined,
          status: "completed",
          enfileirado: false,
          dtAtualizacao: new Date()
        })
        .where("videoId = :videoId", { videoId })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Vídeo com ID ${videoId} não encontrado`);
      }
      this.logger.info(`Transcrição salva para vídeo ${videoId}`);
      return result.raw[0];
    } catch (error: any) {
      this.logger.error(`Erro ao salvar transcrição do vídeo: ${videoId}`, error);
      throw error;
    }
  }

  /**
   * Busca vídeos com erro de transcrição ou processamento
   */
  public async getFailedVideos(): Promise<Video[]> {
    try {
      return await this.repository.createQueryBuilder("video")
        .where("video.transcrito = :transcrito OR video.status = :status", { 
          transcrito: false, 
          status: "error" 
        })
        .andWhere("video.userEmail IS NOT NULL")
        .orderBy("video.dtCriacao", "ASC")
        .getMany();
    } catch (error: any) {
      this.logger.error("Erro ao buscar vídeos com falha:", error);
      throw error;
    }
  }

  /**
   * Verifica o status do Python e dependências
   */
  public async checkTranscriptionSystem(): Promise<{
    pythonAvailable: boolean;
    scriptAvailable: boolean;
    whisperAvailable: boolean;
  }> {
    try {
      const execAsync = promisify(exec);
      const pythonAvailable = await execAsync('python --version')
        .then(() => true)
        .catch(() => false);
      
      const scriptPath = path.join(process.cwd(), "python", "transcribe.py");
      const scriptAvailable = await fs.access(scriptPath)
        .then(() => true)
        .catch(() => false);
      
      let whisperAvailable = false;
      if (pythonAvailable) {
        whisperAvailable = await execAsync('python -c "import whisper"')
          .then(() => true)
          .catch(() => false);
      }
      
      return {
        pythonAvailable,
        scriptAvailable,
        whisperAvailable
      };
    } catch (error: any) {
      this.logger.error("Erro ao verificar sistema de transcrição:", error);
      return {
        pythonAvailable: false,
        scriptAvailable: false,
        whisperAvailable: false
      };
    }
  }

  public async getAllVideos(userId?: string): Promise<Video[]> {
    try {
      let videos;
      if (userId) {
        videos = await this.repository.find({ where: { usuarioId: userId } });
      } else {
        videos = await this.repository.find();
      }
      // Ajustar status conforme a lógica robusta
      return videos.map(v => {
        const transcritoValido = v.transcrito && typeof v.transcrito === 'string' && v.transcrito.trim() !== '' && v.transcrito !== 'ERRO';
        let status: string;
        if (v.status === 'processing') status = 'processing';
        else if (v.status === 'cancelled') status = 'cancelled';
        else if (v.status === 'error' || v.transcrito === 'ERRO') status = 'failed';
        else if (transcritoValido) status = 'completed';
        else status = 'pending';
        return { ...v, status };
      });
    } catch (error: any) {
      this.logger.error('Erro ao buscar todos os vídeos:', error);
      throw error;
    }
  }

  public async getStuckVideos(): Promise<Video[]> {
    try {
      return await this.repository.createQueryBuilder("video")
        .where("video.status = :processing OR video.status = :pending", { processing: "processing", pending: "pending" })
        .orderBy("video.dtCriacao", "ASC")
        .getMany();
    } catch (error: any) {
      this.logger.error("Erro ao buscar vídeos travados:", error);
      throw error;
    }
  }

  async getLastVideoByUserAndFolder(userId: string, folderId: string) {
    return this.repository.findOne({
      where: { usuarioId: userId, pastaId: folderId },
      order: { createdTime: 'DESC' }
    });
  }
}