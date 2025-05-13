import 'reflect-metadata'; // Adicione esta linha no início
import 'dotenv/config';
import { AppDataSource } from './data/data-source';
import { Logger } from './utils/logger';
import { FileSystem } from './utils/file-system';
// Repositories
import { VideoRepository } from './data/repositories/video-repository';
import { CollaboratorRepository } from './data/repositories/collaborator-repository';
// Infrastructure Services
import { WebhookService } from './infrastructure/webhook/webhook-sender';
import { TokenManager } from './infrastructure/auth/token-manager';
import { GoogleAuthService } from './infrastructure/auth/google-auth';
// Domain Services
import { VideoService } from './domain/services/video-service';
import { CollaboratorService } from './domain/services/collaborator-service';
import { TranscriptionService } from './domain/services/transcription-service';
// Core Components
import { VideoProcessor } from './core/transcription/videoProcessor';
import { TranscriptionQueue } from './core/transcription/transcription-queue';
import { DriveWatcher } from './core/drive/drive-watcher';
import { DriveService } from './core/drive/drive-service';
// Scheduler
import { JobScheduler } from './infrastructure/scheduler/job-scheduler';
import { AudioProcessor } from './core/transcription/audio-processor';
import { TranscriptionProcessor } from './core/transcription/transcription-processor';

/**
 * Classe responsável pela inicialização e gerenciamento dos componentes da aplicação
 */
export class Application {
  // Instância única da aplicação (singleton controlado)
  private static instance: Application;

  // Logger
  public readonly logger: Logger;

  // Utils
  public readonly fileSystem: FileSystem;

  // Repositories
  public readonly videoRepository: VideoRepository;
  public readonly collaboratorRepository: CollaboratorRepository;

  // Infrastructure Services
  public readonly webhookService: WebhookService;
  public readonly tokenManager: TokenManager;
  public readonly googleAuthService: GoogleAuthService;

  // Domain Services
  public readonly videoService: VideoService;
  public readonly collaboratorService: CollaboratorService;
  public readonly transcriptionService: TranscriptionService;

  // Core Components
  public readonly videoProcessor: VideoProcessor;
  public readonly transcriptionQueue: TranscriptionQueue;
  public readonly driveWatcher: DriveWatcher;

  // Scheduler
  public readonly jobScheduler: JobScheduler;

  // drive
  public readonly driveService: DriveService;

  // Status da aplicação
  private initialized: boolean = false;

  // audio processor
  private audioProcessor: AudioProcessor;

  //transcription processor
  private transcriptionProcessor: TranscriptionProcessor;

  /**
   * Construtor privado para controle do singleton
   */
  private constructor() {
    if (!AppDataSource.isInitialized) {
      throw new Error("AppDataSource não foi inicializado. Certifique-se de inicializá-lo antes de criar a aplicação.");
    }
    console.log('✅ AppDataSource inicializado. Criando instância da aplicação.');

    // Inicializar o logger primeiro para poder registrar todas as operações
    this.logger = new Logger();
    this.logger.info('Inicializando aplicação...');

    // Inicializar utilitários
    this.fileSystem = new FileSystem(this.logger);

    // Inicializar repositórios
    this.videoRepository = new VideoRepository(this.logger);
    this.collaboratorRepository = new CollaboratorRepository(this.logger);

    // Inicializar serviços de infraestrutura
    this.webhookService = new WebhookService(this.logger);
    this.tokenManager = new TokenManager(this.collaboratorRepository, this.logger);
    this.googleAuthService = new GoogleAuthService(this.logger);

    // Inicializar serviço de autenticação do Google Drive
    this.driveService = new DriveService(this.logger);

    // Inicializar Audio Processor
    this.audioProcessor = new AudioProcessor(this.logger);

    // Inicializar serviços de domínio
    this.videoService = new VideoService(this.videoRepository, this.logger);
    this.collaboratorService = new CollaboratorService(this.collaboratorRepository, this.logger);

    // Inicializar processador de transcrição
    this.transcriptionProcessor = new TranscriptionProcessor(this.logger)

    // Inicializar componentes core
    this.videoProcessor = new VideoProcessor(
      this.logger,
      this.webhookService,
      this.collaboratorRepository,
      this.videoRepository,
      this.tokenManager,
      this.driveService,
      this.audioProcessor,
      this.transcriptionProcessor
    );

    this.transcriptionQueue = new TranscriptionQueue(
      this.logger,
      this.videoProcessor
    );

    this.transcriptionService = new TranscriptionService(
      this.logger,
      this.transcriptionQueue
    );

    this.driveWatcher = new DriveWatcher(
      this.logger,
      this.collaboratorService,
      this.videoService,
      this.tokenManager,
      this.transcriptionQueue // Mesma instância da fila
    );

    // Inicializar scheduler
    this.jobScheduler = new JobScheduler(
      this.logger,
      this.driveWatcher,
      this.videoService,
      this.transcriptionQueue
    );
  }

  /**
   * Obtém a instância única da aplicação
   */
  public static async getInstance(): Promise<Application> {
    if (!AppDataSource.isInitialized) {
      console.log('Inicializando AppDataSource...');
      await AppDataSource.initialize();
      console.log('✅ AppDataSource inicializado com sucesso.');
    }

    if (!Application.instance) {
      Application.instance = new Application();
    }
    return Application.instance;
  }

  /**
   * Inicializa todos os componentes da aplicação
   */
  public async initialize(): Promise<void> {
    if (this.initialized) {
      this.logger.warn('Aplicação já inicializada, ignorando chamada.');
      return;
    }

    try {
      // Inicializar conexão com banco de dados apenas uma vez
      if (!AppDataSource.isInitialized) {
        this.logger.info('Inicializando conexão com o banco de dados...');
        await AppDataSource.initialize();
        this.logger.info('✅ Conexão com o banco de dados estabelecida com sucesso.');
      }

      // Criar diretório temporário
      await this.fileSystem.ensureTempDir();

      // Carregar dados iniciais
      await this.preloadData();

      // Configurar jobs agendados
      this.jobScheduler.setupJobs();
      this.logger.info('✅ Jobs agendados configurados com sucesso.');

      this.initialized = true;
      this.logger.info('✅ Aplicação inicializada com sucesso.');
    } catch (error: any) {
      this.logger.error('❌ Erro ao inicializar a aplicação:', {
        error: error.message,
        stack: error.stack,
      });
      throw error;
    }
  }

  /**
   * Carrega dados iniciais necessários para a aplicação
   */
  private async preloadData(): Promise<void> {
    try {
      this.logger.info('Carregando dados iniciais...');

      // Injetar serviço de transcrição no serviço de vídeo para resolver a dependência circular
      if (!this.videoService || !this.transcriptionService) {
        throw new Error('VideoService ou TranscriptionService não foram inicializados corretamente');
      }

      // Set transcription service in video service
      this.videoService.setTranscriptionService(this.transcriptionService);
      this.logger.info('✅ TranscriptionService injetado no VideoService');

      // Exemplo: Carregar colaboradores para memória
      const collaborators = await this.collaboratorService.getAllActiveCollaborators();
      this.logger.info(`✅ ${collaborators.length} colaboradores ativos carregados.`);

      // Verificar vídeos pendentes
      const pendingVideos = await this.videoService.getPendingVideos();
      this.logger.info(`✅ ${pendingVideos.length} vídeos pendentes encontrados.`);

      // Enfileirar vídeos pendentes
      // Este código é apenas para demonstração, pode ser implementado em um serviço próprio
      if (pendingVideos.length > 0) {
        this.logger.info('Enfileirando vídeos pendentes...');
        for (const video of pendingVideos) {
          if (!video.enfileirado && video.userEmail) {
            const taskId = `pending-${video.videoId}`;
            try {
              // Marcar como enfileirado
              await this.videoService.markVideoAsQueued(video.videoId);

              // Adicionar à fila
              this.transcriptionQueue.add(taskId, {
                videoId: video.videoId,
                webhookUrl: process.env.WEBHOOK_URL || '',
                email: video.userEmail,
                folderId: video.pastaId
              });

              this.logger.info(`✅ Vídeo pendente enfileirado: ${video.videoId}`);
            } catch (err: any) {
              this.logger.error(`❌ Erro ao enfileirar vídeo pendente ${video.videoId}:`, err);
            }
          }
        }
      }
    } catch (error: any) {
      this.logger.error('❌ Erro ao carregar dados iniciais:', error);
      throw error;
    }
  }

  /**
   * Executa tarefas ao encerrar a aplicação
   */
  public async shutdown(): Promise<void> {
    try {
      this.logger.info('Encerrando a aplicação...');

      // Fechar conexão com o banco de dados
      if (AppDataSource.isInitialized) {
        await AppDataSource.destroy();
        this.logger.info('Conexão com o banco de dados fechada.');
      }

      this.logger.info('Aplicação encerrada com sucesso.');
    } catch (error: any) {
      this.logger.error('Erro ao encerrar a aplicação:', error);
      // Em caso de erro no encerramento, forçar a saída
      process.exit(1);
    }
  }

  /**
   * Retorna estatísticas da aplicação
   */
  public getStatus(): Record<string, any> {
    return {
      initialized: this.initialized,
      database: AppDataSource.isInitialized,
      queue: {
        waiting: this.transcriptionQueue.getQueueSize(),
        processing: this.transcriptionQueue.getProcessingSize()
      }
    };
  }
}

// Configurar handler para encerramento limpo
process.on('SIGINT', async () => {
  console.log('\nRecebido sinal de interrupção. Encerrando aplicação...');
  const app = await Application.getInstance();
  await app.shutdown();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\nRecebido sinal de término. Encerrando aplicação...');
  const app = await Application.getInstance();
  await app.shutdown();
  process.exit(0);
});

// Exportar uma instância singleton
export const appPromise = Application.getInstance();
