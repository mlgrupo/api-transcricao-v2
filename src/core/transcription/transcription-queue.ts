import { Logger } from "../../utils/logger";
import { VideoProcessor } from "./videoProcessor";

interface QueueJob {
  videoId: string;
  webhookUrl: string;
  email: string;
  folderId?: string;
  priority?: 'high' | 'normal' | 'low';
  resourceLimit?: {
    maxCpuPercent?: number;
    maxMemoryGB?: number;
  };
}

export class TranscriptionQueue {
  private queue: Map<string, QueueJob>;
  private processing: Set<string>;
  private maxConcurrentJobs: number;
  // Mapa de controladores de cancelamento por videoId
  private cancellationMap: Map<string, { cancelled: boolean }> = new Map();
  // Controle de recursos por job
  private resourceUsage: Map<string, { cpuPercent: number; memoryGB: number }> = new Map();

  constructor(
    private logger: Logger,
    private videoProcessor: VideoProcessor,
  ) {
    this.queue = new Map();
    this.processing = new Set();
    // Processamento sequencial: apenas 1 job por vez
    this.maxConcurrentJobs = parseInt(process.env.MAX_CONCURRENT_JOBS || "1", 10);

    this.logger.info(`Fila de transcrição inicializada com limite de ${this.maxConcurrentJobs} jobs simultâneos`);
  }

  public add(taskId: string, job: QueueJob): void {
    if (this.queue.has(taskId) || this.processing.has(taskId)) {
      this.logger.warn("Tarefa já existente na fila ou em processamento", { taskId });
      return;
    }
    
    // Configurar limites de recursos para MÁXIMO CPU
    if (!job.resourceLimit) {
      job.resourceLimit = {
        maxCpuPercent: 100,  // Máximo 100% CPU (todos os 8 vCPUs)
        maxMemoryGB: 26      // Máximo 26GB RAM (de 28GB total)
      };
    }
    
    if (!job.priority) {
      job.priority = 'normal';
    }
    
    this.logger.info('Adicionando job à fila', { 
      taskId, 
      videoId: job.videoId,
      priority: job.priority,
      resourceLimit: job.resourceLimit
    });
    this.queue.set(taskId, job);
    this._tryToProcess();
  }

  /**
   * Adiciona um job no início da fila (prioridade máxima)
   */
  public addNow(taskId: string, job: QueueJob): void {
    if (this.queue.has(taskId) || this.processing.has(taskId)) {
      this.logger.warn("Tarefa já existente na fila ou em processamento", { taskId });
      return;
    }
    this.logger.info('Adicionando job prioritário à fila', { taskId, ...job });
    // Inserir no início: recriar o Map com o novo job primeiro
    const newQueue = new Map<string, QueueJob>([[taskId, job], ...this.queue]);
    this.queue = newQueue;
    this._tryToProcess();
  }

  public getQueueSize(): number {
    return this.queue.size;
  }

  public getProcessingSize(): number {
    return this.processing.size;
  }

  public getQueueStatus(): { 
    queued: number; 
    processing: number; 
    totalCpuUsage: number; 
    totalMemoryUsage: number;
    resourceUsage: Array<{ taskId: string; cpuPercent: number; memoryGB: number }>;
  } {
    const totalCpuUsage = this.getTotalCpuUsage();
    const totalMemoryUsage = this.getTotalMemoryUsage();
    
    const resourceUsage = Array.from(this.resourceUsage.entries()).map(([taskId, usage]) => ({
      taskId,
      cpuPercent: usage.cpuPercent,
      memoryGB: usage.memoryGB
    }));

    return {
      queued: this.queue.size,
      processing: this.processing.size,
      totalCpuUsage,
      totalMemoryUsage,
      resourceUsage
    };
  }

  /**
   * Retorna as chaves dos jobs na fila
   */
  public getQueueKeys(): string[] {
    return Array.from(this.queue.keys());
  }

  /**
   * Remove um job da fila pelo taskId
   */
  public removeByTaskId(taskId: string): void {
    this.queue.delete(taskId);
    this.logger.info(`Removido da fila: ${taskId}`);
  }

  /**
   * Cancela um job em andamento ou na fila
   */
  public cancelJob(videoId: string): void {
    // Cancelar se estiver em processamento
    const controller = this.cancellationMap.get(videoId);
    if (controller) {
      controller.cancelled = true;
      this.logger.info(`Cancelamento solicitado para o vídeo ${videoId}`);
    }
    // Remover da fila (caso ainda não tenha iniciado)
    for (const [taskId, job] of this.queue.entries()) {
      if (job.videoId === videoId) {
        this.queue.delete(taskId);
        this.logger.info(`Removido da fila (por cancelamento): ${taskId}`);
      }
    }
  }

  /**
   * Calcula o uso total de CPU dos jobs em processamento
   */
  private getTotalCpuUsage(): number {
    let totalCpu = 0;
    for (const usage of this.resourceUsage.values()) {
      totalCpu += usage.cpuPercent;
    }
    return totalCpu;
  }

  /**
   * Calcula o uso total de memória dos jobs em processamento
   */
  private getTotalMemoryUsage(): number {
    let totalMemory = 0;
    for (const usage of this.resourceUsage.values()) {
      totalMemory += usage.memoryGB;
    }
    return totalMemory;
  }

  /**
   * Verifica se há recursos suficientes para processar um job
   */
  private canProcessJob(job: QueueJob, currentCpuUsage: number, currentMemoryUsage: number): boolean {
    const requiredCpu = job.resourceLimit?.maxCpuPercent || 100;
    const requiredMemory = job.resourceLimit?.maxMemoryGB || 26;
    
    // Limites para MÁXIMO CPU - usar tudo
    const availableCpu = 100 - currentCpuUsage;  // 100% disponível
    const availableMemory = 28 - currentMemoryUsage;
    
    return availableCpu >= requiredCpu && availableMemory >= requiredMemory;
  }

  private _tryToProcess(): void {
    if (this.processing.size >= this.maxConcurrentJobs) {
      this.logger.info('Limite de jobs paralelos atingido, aguardando...', {
        processing: this.processing.size,
        maxConcurrent: this.maxConcurrentJobs
      });
      return;
    }

    // Verificar uso total de recursos
    const totalCpuUsage = this.getTotalCpuUsage();
    const totalMemoryUsage = this.getTotalMemoryUsage();
    
    this.logger.info('Verificando recursos disponíveis', {
      totalCpuUsage: `${totalCpuUsage.toFixed(1)}%`,
      totalMemoryUsage: `${totalMemoryUsage.toFixed(1)}GB`,
      processing: this.processing.size
    });

    // Pegar primeiros jobs da fila que não estão em processamento
    const availableTasks = Array.from(this.queue.keys())
      .filter(id => !this.processing.has(id));

    for (const taskId of availableTasks) {
      if (this.processing.size >= this.maxConcurrentJobs) break;
      
      const job = this.queue.get(taskId);
      if (!job) continue;
      
      // Verificar se há recursos suficientes para este job
      const canProcess = this.canProcessJob(job, totalCpuUsage, totalMemoryUsage);
      
      if (canProcess) {
        this._process(taskId);
      } else {
        this.logger.info('Recursos insuficientes para processar job', {
          taskId,
          videoId: job.videoId,
          requiredCpu: job.resourceLimit?.maxCpuPercent,
          requiredMemory: job.resourceLimit?.maxMemoryGB,
          availableCpu: 100 - totalCpuUsage,
          availableMemory: 32 - totalMemoryUsage
        });
        break; // Parar de tentar processar mais jobs
      }
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

    // Criar controlador de cancelamento
    const cancelObj = { cancelled: false };
    this.cancellationMap.set(videoId, cancelObj);

    // Registrar uso de recursos estimado
    this.resourceUsage.set(taskId, {
      cpuPercent: job.resourceLimit?.maxCpuPercent || 100,
      memoryGB: job.resourceLimit?.maxMemoryGB || 26
    });

    this.logger.info('Iniciando processamento do job', { 
      taskId, 
      videoId, 
      email,
      resourceLimit: job.resourceLimit
    });

    try {
      await this.videoProcessor.processVideo(videoId, webhookUrl, email, folderId, taskId, cancelObj);
      this.logger.info('✅ Job finalizado com sucesso', { taskId, videoId });
    } catch (error: any) {
      this.logger.error('❌ Erro no job', { taskId, videoId, error: error.message });
    } finally {
      this.processing.delete(taskId);
      this.cancellationMap.delete(videoId);
      this.resourceUsage.delete(taskId);
      this._tryToProcess();
    }
  }
}
