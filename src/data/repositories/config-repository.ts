import { Repository } from "typeorm";
import { AppDataSource } from "../data-source";
import { SystemConfig } from "../../domain/models/SystemConfig";
import { Logger } from "../../utils/logger";

export class ConfigRepository {
  private repository: Repository<SystemConfig>;
  private logger: Logger;

  constructor(logger: Logger) {
    this.repository = AppDataSource.getRepository(SystemConfig);
    this.logger = logger;
  }

  public async getConfig(key: string, userId?: string | null): Promise<any> {
    try {
      const where: any = { key };
      if (typeof userId !== 'undefined') where.userId = userId;
      const config = await this.repository.findOne({ where });
      return config ? config.value : null;
    } catch (error: any) {
      this.logger.error(`Erro ao buscar configuração ${key}:`, error);
      throw error;
    }
  }

  public async setConfig(key: string, value: any, userId?: string | null): Promise<void> {
    try {
      const where: any = { key };
      if (typeof userId !== 'undefined') where.userId = userId;
      let config = await this.repository.findOne({ where });
      if (config) {
        config.value = value;
        config.updatedAt = new Date();
      } else {
        config = this.repository.create();
        config.key = key;
        config.value = value;
        config.userId = userId;
        config.createdAt = new Date();
        config.updatedAt = new Date();
      }
      await this.repository.save(config);
      this.logger.info(`Configuração ${key} salva com sucesso para userId=${userId}`);
    } catch (error: any) {
      this.logger.error(`Erro ao salvar configuração ${key}:`, error);
      throw error;
    }
  }

  public async getRootFolders(userId: string): Promise<string[]> {
    try {
      const folders = await this.getConfig("root_folder", userId);
      if (Array.isArray(folders)) {
        return folders;
      } else if (typeof folders === 'string') {
        return [folders];
      }
      // Se não houver config, retorna array vazio
      return [];
    } catch (error: any) {
      this.logger.error("Erro ao buscar pastas raiz:", error);
      return [];
    }
  }

  public async setRootFolders(folders: string[], userId?: string): Promise<void> {
    try {
      await this.setConfig("root_folder", folders, userId);
    } catch (error: any) {
      this.logger.error("Erro ao salvar pastas raiz:", error);
      throw error;
    }
  }

  public async deleteRootFolders(userId: string): Promise<void> {
    try {
      const where: any = { key: 'root_folder' };
      if (typeof userId !== 'undefined') where.userId = userId;
      await this.repository.delete(where);
      this.logger.info(`Configuração root_folder removida para userId=${userId}`);
    } catch (error: any) {
      this.logger.error('Erro ao remover configuração root_folder:', error);
      throw error;
    }
  }

  public async getTranscriptionConfig(userId: string): Promise<{
    transcriptionFolder?: string;
    moveVideoAfterTranscription: boolean;
    videoDestinationFolder?: string;
  }> {
    try {
      const config = await this.getConfig("transcription_config", userId);
      if (config) {
        return {
          transcriptionFolder: config.transcriptionFolder || undefined,
          moveVideoAfterTranscription: Boolean(config.moveVideoAfterTranscription),
          videoDestinationFolder: config.videoDestinationFolder || undefined
        };
      }
      return {
        transcriptionFolder: undefined,
        moveVideoAfterTranscription: false,
        videoDestinationFolder: undefined
      };
    } catch (error: any) {
      this.logger.error("Erro ao buscar configuração de transcrição:", error);
      return {
        transcriptionFolder: undefined,
        moveVideoAfterTranscription: false,
        videoDestinationFolder: undefined
      };
    }
  }

  public async setTranscriptionConfig(config: {
    transcriptionFolder?: string;
    moveVideoAfterTranscription: boolean;
    videoDestinationFolder?: string;
  }, userId: string): Promise<void> {
    try {
      await this.setConfig("transcription_config", config, userId);
    } catch (error: any) {
      this.logger.error("Erro ao salvar configuração de transcrição:", error);
      throw error;
    }
  }

  // Webhooks continuam globais (userId = null)
  public async getWebhooks(): Promise<Array<{
    id: string;
    url: string;
    name: string;
    description: string;
    events: string[];
    active: boolean;
  }>> {
    try {
      const webhooks = await this.getConfig("webhooks", null);
      if (Array.isArray(webhooks)) {
        return webhooks;
      }
      return [];
    } catch (error: any) {
      this.logger.error("Erro ao buscar webhooks:", error);
      return [];
    }
  }

  public async setWebhooks(webhooks: Array<{
    id: string;
    url: string;
    name: string;
    description: string;
    events: string[];
    active: boolean;
  }>): Promise<void> {
    try {
      await this.setConfig("webhooks", webhooks, null);
    } catch (error: any) {
      this.logger.error("Erro ao salvar webhooks:", error);
      throw error;
    }
  }
} 