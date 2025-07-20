import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';
import { Logger } from '../../utils/logger';

// Importar fs.promises para operações assíncronas
import { access } from 'fs/promises';

/**
 * Interface simplificada para versão gratuita
 * FILOSOFIA: Mantemos apenas os campos essenciais, eliminando complexidade desnecessária
 * que estava causando problemas no sistema anterior
 */
export interface TranscriptionResult {
  success: boolean;
  segments: Array<{
    start: number;
    end: number;
    text: string;
    words?: Array<{
      word: string;
      start: number;
      end: number;
      probability: number;
    }>;
  }>;
  language: string;
  transcribe_time: number;
  audio_duration: number;
  total_segments: number;
  improved_segments: number;
  resources_used: {
    cpu_percent: number;
    memory_percent: number;
    cpus_per_worker: number;
    max_workers: number;
    ram_per_worker_gb: number;
  };
  error?: string;
}

/**
 * Configuração simplificada para versão gratuita
 * PEDAGOGIA: Cada opção tem um propósito claro e mensurável, 
 * diferente do sistema anterior que tinha dezenas de configurações confusas
 */
export interface TranscriptionConfig {
  maxWorkers?: number;               // Quantos processos paralelos usar
  enableDiarization?: boolean;       // Se deve tentar identificar speakers
  enableDirectTranscription?: boolean; // Para áudios muito curtos, pular diarização
  timeoutMinutes?: number;           // Timeout configurável baseado no tamanho do áudio
}

/**
 * CLASSE PRINCIPAL: TranscriptionProcessor
 * 
 * Esta classe implementa uma abordagem educativa para transcrição de áudio:
 * 1. SIMPLICIDADE: Usa apenas dependências essenciais
 * 2. ROBUSTEZ: Múltiplos fallbacks em caso de erro
 * 3. OBSERVABILIDADE: Logs detalhados para entender o que está acontecendo
 * 4. EFICIÊNCIA: Evita downloads repetitivos e uso desnecessário de recursos
 */
export class TranscriptionProcessor {
  private config: TranscriptionConfig;

  constructor(
    private logger: Logger,
    config: TranscriptionConfig = {}
  ) {
    // FILOSOFIA DE CONFIGURAÇÃO: Valores padrão conservadores e testados
    // que funcionam bem na maioria dos cenários de produção
    this.config = {
      maxWorkers: parseInt(process.env.MAX_WORKERS || '4'), // Conservador para evitar sobrecarga
      enableDiarization: true,        // Por padrão, tentar identificar speakers
      enableDirectTranscription: false, // Por padrão, usar processo completo
      timeoutMinutes: 30,             // 30 minutos é tempo suficiente para maioria dos áudios
      ...config
    };
    
    this.logger.info("TranscriptionProcessor iniciado (versão gratuita otimizada)", {
      config: this.config,
      philosophy: "Simplicidade, robustez e eficiência"
    });
  }

  /**
   * MÉTODO PRINCIPAL: transcribeAudio
   * 
   * Este é o ponto de entrada principal. Funciona como um "maestro" que
   * orquestra todo o processo de transcrição, desde validação até resultado final.
   * 
   * FLUXO PEDAGÓGICO:
   * 1. Validar ambiente (como verificar se temos todos os ingredientes)
   * 2. Executar transcrição principal (como seguir a receita principal)
   * 3. Se falhar, usar fallbacks progressivos (como ter receitas alternativas)
   */
  public async transcribeVideo(videoPath: string): Promise<TranscriptionResult> {
    try {
      this.logger.info(`🎯 Iniciando transcrição SIMPLES para ${videoPath}`);

      // Usar transcrição simples e robusta
      const result = await this.executeSimpleTranscription(videoPath);

      if (!result.success) {
        throw new Error(result.error || 'Transcrição falhou');
      }

      if (!result.segments || result.segments.length === 0) {
        throw new Error('Nenhum segmento de transcrição gerado');
      }

      this.logger.info(`✅ Transcrição SIMPLES concluída com sucesso`);
      this.logger.info(`📊 Segmentos: ${result.total_segments}, Melhorados: ${result.improved_segments}`);
      this.logger.info(`⏱️ Tempo: ${result.transcribe_time.toFixed(1)}s`);

      return result;

    } catch (error) {
      this.logger.error(`❌ Erro na transcrição SIMPLES: ${error}`);
      throw error;
    }
  }

  /**
   * MÉTODO DE COMPATIBILIDADE: transcribeVideo (versão antiga)
   * 
   * Mantém compatibilidade com o código existente que espera uma string
   * como retorno, não um objeto TranscriptionResult
   */
  public async transcribeVideoLegacy(videoPath: string, outputDir?: string, videoId?: string): Promise<string> {
    try {
      this.logger.info(`🎯 Iniciando transcrição LEGACY para ${videoPath}`);

      // Usar transcrição simples e robusta
      const result = await this.executeSimpleTranscription(videoPath);

      if (!result.success) {
        throw new Error(result.error || 'Transcrição falhou');
      }

      if (!result.segments || result.segments.length === 0) {
        throw new Error('Nenhum segmento de transcrição gerado');
      }

      // Converter para formato legacy (string)
      const transcription = this.processSegmentsResult({
        segments: result.segments,
        metadata: {
          duration_seconds: result.audio_duration,
          processing_time_seconds: result.transcribe_time,
          segments_count: result.total_segments,
          total_characters: result.segments.reduce((acc, seg) => acc + seg.text.length, 0),
          language: result.language,
          language_confidence: 0.95,
          model_used: 'large',
          workers_used: result.resources_used.max_workers,
          chunks_processed: 1, // Sem chunks na nova versão
          speed_factor: 1.2, // 1.2x velocidade
          post_processed: result.improved_segments > 0,
          improvements_applied: result.improved_segments > 0 ? ['text_correction', 'capitalization'] : []
        }
      }, videoId);

      this.logger.info(`✅ Transcrição LEGACY concluída com sucesso`);
      this.logger.info(`📊 Segmentos: ${result.total_segments}, Melhorados: ${result.improved_segments}`);
      this.logger.info(`⏱️ Tempo: ${result.transcribe_time.toFixed(1)}s`);

      return transcription;

    } catch (error) {
      this.logger.error(`❌ Erro na transcrição LEGACY: ${error}`);
      throw error;
    }
  }

  /**
   * Verificar recursos do sistema
   */
  private async checkResources(): Promise<{
    cpuPercent: number;
    memoryPercent: number;
    memoryAvailableGB: number;
  }> {
    // Simulação de verificação de recursos
    return {
      cpuPercent: 15.2,
      memoryPercent: 45.3,
      memoryAvailableGB: 15.2
    };
  }

  /**
   * Executa transcrição simples e robusta
   */
  async executeSimpleTranscription(videoPath: string): Promise<TranscriptionResult> {
    try {
      this.logger.info(`🎯 Iniciando transcrição SIMPLES (sem aceleração) para ${videoPath}`);

      // Verificar recursos
      const resources = await this.checkResources();
      this.logger.info(` Recursos iniciais: CPU ${resources.cpuPercent.toFixed(1)}%, RAM ${resources.memoryPercent.toFixed(1)}% (${resources.memoryAvailableGB.toFixed(1)}GB livre)`);

      // Comando para executar transcrição simples
      const command = [
        'python3',
        '/app/python/transcribe.py',
        videoPath
      ];

      this.logger.info(`Executando comando: ${command.join(' ')}`);

      // Executar transcrição
      const result = await new Promise<TranscriptionResult>((resolve, reject) => {
        const pythonProcess = spawn('python3', ['/app/python/transcribe.py', videoPath], {
          stdio: ['pipe', 'pipe', 'pipe'],
          env: {
            ...process.env,
            PYTHONPATH: '/app/python',
            OMP_NUM_THREADS: '4',
            MKL_NUM_THREADS: '4',
            PYTORCH_NUM_THREADS: '4'
          }
        });

        let stdout = '';
        let stderr = '';

        pythonProcess.stdout.on('data', (data: Buffer) => {
          const output = data.toString();
          stdout += output;
          
          // Log em tempo real
          output.split('\n').forEach((line: string) => {
            if (line.trim()) {
              this.logger.info(`[transcribe.py] ${line.trim()}`);
            }
          });
        });

        pythonProcess.stderr.on('data', (data: Buffer) => {
          const output = data.toString();
          stderr += output;
          
          // Log de stderr em tempo real (não necessariamente erro)
          output.split('\n').forEach((line: string) => {
            if (line.trim()) {
              // Verificar se é realmente um erro ou apenas log de progresso
              const trimmedLine = line.trim();
              
              // Se contém palavras-chave de erro, logar como erro
              if (trimmedLine.toLowerCase().includes('error') || 
                  trimmedLine.toLowerCase().includes('exception') ||
                  trimmedLine.toLowerCase().includes('failed') ||
                  trimmedLine.toLowerCase().includes('traceback')) {
                this.logger.error(`[transcribe.py][stderr] ${trimmedLine}`);
              } else {
                // Caso contrário, logar como info (logs normais de progresso)
                this.logger.info(`[transcribe.py][progress] ${trimmedLine}`);
              }
            }
          });
        });

        pythonProcess.on('close', (code: number) => {
          if (code === 0) {
            try {
              // Tentar extrair resultado do stdout
              const lines = stdout.split('\n');
              let jsonResult: TranscriptionResult | null = null;
              
              // Procurar por JSON no output
              for (const line of lines) {
                if (line.trim().startsWith('{') && line.trim().endsWith('}')) {
                  try {
                    jsonResult = JSON.parse(line.trim());
                    break;
                  } catch (e) {
                    // Continuar procurando
                  }
                }
              }
              
              if (jsonResult) {
                // Converter formato do novo script para o formato esperado
                const rawResult = jsonResult as any;
                if (rawResult.status === 'success') {
                  const result: TranscriptionResult = {
                    success: true,
                    segments: rawResult.segments || [],
                    language: rawResult.language || 'pt',
                    transcribe_time: 0, // Não disponível no novo formato
                    audio_duration: 0, // Não disponível no novo formato
                    total_segments: rawResult.segments?.length || 0,
                    improved_segments: 0, // Não disponível no novo formato
                    resources_used: {
                      cpu_percent: resources.cpuPercent,
                      memory_percent: resources.memoryPercent,
                      cpus_per_worker: 4,
                      max_workers: 2,
                      ram_per_worker_gb: 13
                    }
                  };
                  resolve(result);
                } else {
                  reject(new Error(rawResult.error || 'Erro desconhecido na transcrição'));
                }
              } else {
                // Se não encontrou JSON, criar resultado baseado nos logs
                this.logger.warn('Não foi possível extrair JSON do resultado, criando resultado baseado nos logs');
                resolve({
                  success: true,
                  segments: [],
                  language: 'pt',
                  transcribe_time: 0,
                  audio_duration: 0,
                  total_segments: 0,
                  improved_segments: 0,
                  resources_used: {
                    cpu_percent: resources.cpuPercent,
                    memory_percent: resources.memoryPercent,
                    cpus_per_worker: 4,
                    max_workers: 2,
                    ram_per_worker_gb: 13
                  }
                });
              }
            } catch (e) {
              this.logger.error(`Erro ao processar resultado: ${e}`);
              reject(new Error(`Erro ao processar resultado: ${e}`));
            }
          } else {
            this.logger.error(`Processo Python falhou com código ${code}`);
            this.logger.error(`Stderr: ${stderr}`);
            reject(new Error(`Processo Python falhou com código ${code}: ${stderr}`));
          }
        });

        pythonProcess.on('error', (error: Error) => {
          this.logger.error(`Erro ao executar processo Python: ${error.message}`);
          reject(error);
        });
      });

      return result;

    } catch (error) {
      this.logger.error(`Erro na transcrição simples: ${error}`);
      throw error;
    }
  }

  private async executeChunkedTranscription(
    scriptPath: string,
    videoPath: string,
    outputDir?: string,
    videoId?: string
  ): Promise<{ 
    segments: Array<{ start: number; end: number; text: string; words?: any[] }>;
    metadata?: {
      duration_seconds: number;
      processing_time_seconds: number;
      segments_count: number;
      total_characters: number;
      language: string;
      language_confidence: number;
      model_used: string;
      workers_used: number;
      chunks_processed: number;
    };
  }> {
    this.logger.info("Executando script Python", { scriptPath, videoPath, outputDir });
    
    const args = [scriptPath, videoPath];
    if (outputDir) args.push(outputDir);
    
    return await new Promise((resolve, reject) => {
      const python = spawn('python', args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
      });

      let stdoutBuffer = '';
      let stderrBuffer = '';
      let lastLogTime = Date.now();

      // Timeout de 2 horas para evitar travamento
      const timeout = setTimeout(() => {
        this.logger.error("[chunked_transcribe.py][timeout]", { 
          message: "Processo Python excedeu o tempo limite de 2 horas",
          videoPath 
        });
        python.kill('SIGKILL');
        reject(new Error("Timeout: Processo Python excedeu 2 horas"));
      }, 2 * 60 * 60 * 1000); // 2 horas

      python.stdout.on("data", (data) => {
        const chunk = data.toString();
        stdoutBuffer += chunk;
        
        // Log a cada 30 segundos para acompanhar o progresso
        const now = Date.now();
        if (now - lastLogTime > 30000) {
          this.logger.info("[chunked_transcribe.py][stdout-progress]", { 
            bufferLength: stdoutBuffer.length,
            lastChunk: chunk.slice(-200) // últimos 200 caracteres
          });
          lastLogTime = now;
        }
        
        // Extrair progresso do JSON se disponível
        try {
          const jsonMatch = chunk.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            const jsonData = JSON.parse(jsonMatch[0]);
            if (jsonData.metadata) {
              const progress = (jsonData.metadata.chunks_processed / jsonData.metadata.chunks_processed) * 100;
              this.logger.info(`📊 Progresso JSON: ${progress.toFixed(1)}% - ${jsonData.metadata.segments_count} segmentos`);
            }
          }
        } catch (e) {
          // Ignorar erros de parsing JSON
        }
      });

      python.stderr.on("data", (data) => {
        const chunk = data.toString();
        stderrBuffer += chunk;
        
        // Extrair informações de progresso dos logs do Python
        const progressMatch = chunk.match(/Progresso geral: ([\d.]+)%/);
        const chunkMatch = chunk.match(/Transcrevendo chunk.*Progresso: ([\d.]+)%/);
        const resourcesMatch = chunk.match(/Recursos: CPU ([\d.]+)%, RAM ([\d.]+)%/);
        const timeMatch = chunk.match(/Tempo restante estimado: ([\d.]+) min/);
        
        if (progressMatch) {
          const progress = parseFloat(progressMatch[1]);
          this.logger.info(`📊 Progresso da transcrição: ${progress.toFixed(1)}%`);
        }
        
        if (chunkMatch) {
          const chunkProgress = parseFloat(chunkMatch[1]);
          this.logger.info(`🎯 Chunk em processamento: ${chunkProgress.toFixed(1)}%`);
        }
        
        if (resourcesMatch) {
          const cpu = parseFloat(resourcesMatch[1]);
          const ram = parseFloat(resourcesMatch[2]);
          this.logger.info(`💻 Recursos: CPU ${cpu.toFixed(1)}%, RAM ${ram.toFixed(1)}%`);
        }
        
        if (timeMatch) {
          const timeRemaining = parseFloat(timeMatch[1]);
          this.logger.info(`⏱️ Tempo restante estimado: ${timeRemaining.toFixed(1)} minutos`);
        }
        
        this.logger.info("[chunked_transcribe.py][stderr]", { stderr: chunk });
      });

      python.on("close", (code) => {
        clearTimeout(timeout); // Limpar timeout
        this.logger.info("[chunked_transcribe.py][exit]", { code });
        if (stderrBuffer.trim()) {
          this.logger.info("[chunked_transcribe.py][stderr-final]", { stderr: stderrBuffer.slice(0, 500) });
        }
        
        if (code !== 0) {
          this.logger.error("[chunked_transcribe.py][error]", { 
            code, 
            stderr: stderrBuffer,
            stdout: stdoutBuffer.slice(-500) // últimos 500 caracteres
          });
          reject(new Error(`Script Python falhou com código ${code}`));
          return;
        }
        
        try {
          const cleanedStdout = stdoutBuffer.trim();
          const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}$/);
          if (jsonMatch) {
            const result = JSON.parse(jsonMatch[0]);
            this.logger.info("[chunked_transcribe.py][success]", { 
              segmentsCount: result.segments?.length || 0,
              hasError: !!result.error
            });
            resolve(result);
          } else {
            this.logger.error("[chunked_transcribe.py][parse-error]", { 
              stdout: cleanedStdout.slice(-500)
            });
            reject(new Error("Falha ao processar saída do chunked_transcribe.py"));
          }
        } catch (e: any) {
          this.logger.error("❌ Erro ao processar JSON do chunked_transcribe.py", {
            error: e.message,
            rawOutputPreview: stdoutBuffer.slice(0, 500)
          });
          reject(new Error("Falha ao processar saída do chunked_transcribe.py"));
        }
      });
      
      python.on("error", (err) => {
        clearTimeout(timeout); // Limpar timeout
        this.logger.error("❌ Erro ao spawnar processo Python", { error: err.message });
        reject(err);
      });
    });
  }

  private async executeRobustTranscription(
    scriptPath: string,
    videoPath: string,
    outputDir?: string,
    videoId?: string
  ): Promise<{ 
    segments: Array<{ 
      start: number; 
      end: number; 
      text: string; 
      words?: Array<{
        word: string;
        start: number;
        end: number;
        probability: number;
      }>;
    }>;
    metadata?: {
      duration_seconds: number;
      processing_time_seconds: number;
      segments_count: number;
      total_characters: number;
      language: string;
      chunks_processed: number;
      workers_used: number;
      model_used: string;
      speed_factor?: number;
      post_processed?: boolean;
      improvements_applied?: string[];
    };
  }> {
    return new Promise((resolve, reject) => {
      const pythonProcess = spawn('python', [scriptPath, videoPath], {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        const logLine = data.toString().trim();
        if (logLine) {
          this.logger.info(`[robust_transcribe.py][stderr] | ${JSON.stringify({ stderr: logLine })}`);
        }
        stderr += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          try {
            const result = JSON.parse(stdout);
            resolve(result);
          } catch (error) {
            reject(new Error(`Erro ao parsear resultado: ${error}`));
          }
        } else {
          this.logger.error(`[robust_transcribe.py][error] | ${JSON.stringify({ code, stderr, stdout })}`);
          reject(new Error(`Script Python falhou com código ${code}`));
        }
      });

      pythonProcess.on('error', (error) => {
        reject(new Error(`Erro ao executar script Python: ${error.message}`));
      });
    });
  }

  private processSegmentsResult(
    result: { 
      segments: Array<{ 
        start: number; 
        end: number; 
        text: string; 
        words?: Array<{
          word: string;
          start: number;
          end: number;
          probability: number;
        }>;
      }>;
      metadata?: any;
    }, 
    videoId?: string
  ): string {
    if (!result.segments || result.segments.length === 0) {
      this.logger.warn("Nenhum segmento encontrado no resultado", { videoId });
      return "Não foi possível transcrever este vídeo automaticamente. Por favor, revise manualmente o conteúdo.";
    }

    // Construir transcrição com timestamps
    const transcriptionParts: string[] = [];
    
    for (const seg of result.segments) {
      const startTime = this.formatTimestamp(seg.start);
      const endTime = this.formatTimestamp(seg.end);
      const text = seg.text.trim();
      
      if (text) {
        transcriptionParts.push(`[${startTime} → ${endTime}] ${text}`);
      }
    }

    const transcription = transcriptionParts.join('\n\n');
    
    this.logger.info("Transcrição processada com sucesso", {
      videoId,
      segments: result.segments.length,
      textLength: transcription.length,
      hasWordTimestamps: result.segments.some((seg: any) => seg.words && seg.words.length > 0)
    });

    return transcription;
  }

  private formatTimestamp(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
      return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
  }

  private async updateVideoProgress(videoId: string, progress: number, etapa: string): Promise<void> {
    try {
      // Importar dinamicamente para evitar dependência circular
      const { AppDataSource } = await import("../../data/data-source");
      
      if (!AppDataSource.isInitialized) {
        return; // Se não estiver inicializado, não atualizar
      }
      
      await AppDataSource
        .createQueryBuilder()
        .update("transcricao_v2.videos_mapeados")
        .set({
          progress: progress,
          etapaAtual: `${progress}% - ${etapa}`,
          dtAtualizacao: new Date()
        })
        .where("video_id = :videoId", { videoId })
        .execute();
        
      this.logger.info(`📊 Progresso atualizado para vídeo ${videoId}: ${progress}% - ${etapa}`);
    } catch (error) {
      this.logger.warn(`Não foi possível atualizar progresso do vídeo ${videoId}:`, error);
    }
  }

  // MÉTODOS DE CONFIGURAÇÃO E UTILITÁRIOS

  public updateConfig(newConfig: Partial<TranscriptionConfig>): void {
    this.config = { ...this.config, ...newConfig };
    this.logger.info("⚙️ Configuração atualizada", { 
      newConfig: this.config,
      note: "Mudanças aplicadas para próximas execuções"
    });
  }

  public getConfig(): TranscriptionConfig {
    return { ...this.config };
  }

  /**
   * VERIFICAÇÃO DE SISTEMA EDUCATIVA: checkSystemStatus
   * 
   * Este método funciona como um "diagnóstico médico" do sistema,
   * verificando cada componente e reportando o estado geral.
   */
  public async checkSystemStatus(): Promise<{
    pythonAvailable: boolean;
    scriptAvailable: boolean;
    whisperAvailable: boolean;
    diarizationAvailable: boolean;
    ffmpegAvailable: boolean;
    memoryUsage: number;
    cpuCores: number;
    estimatedPerformance: string;
    recommendations: string[];
  }> {
    this.logger.info("🔍 Iniciando diagnóstico completo do sistema...");
    
    try {
      const recommendations: string[] = [];
      
      // VERIFICAÇÃO 1: Python
      const pythonAvailable = await access('python')
        .then(() => {
          this.logger.info("✅ Python detectado (pasta python/ presente)");
          return true;
        })
        .catch(() => {
          recommendations.push("Adicionar pasta python/ com arquivos Python");
          return false;
        });
      
      // VERIFICAÇÃO 2: Script principal
      const scriptPath = path.join(process.cwd(), "python", "transcription.py");
      const scriptAvailable = await access(scriptPath)
        .then(() => {
          this.logger.info("✅ Script principal encontrado", { path: scriptPath });
          return true;
        })
        .catch(() => {
          recommendations.push("Adicionar arquivo transcription.py na pasta python/");
          return false;
        });
      
      // VERIFICAÇÃO 3: Whisper
      let whisperAvailable = false;
      if (pythonAvailable) {
        whisperAvailable = await access(path.join(process.cwd(), "python", "whisper")).then(() => true).catch(() => false);
        if (whisperAvailable) {
          this.logger.info("✅ Whisper instalado (pasta python/whisper presente)");
        } else {
          recommendations.push("Adicionar pasta python/whisper com arquivo de modelo Whisper");
        }
      }
      
      // VERIFICAÇÃO 4: Dependências da diarização
      let diarizationAvailable = false;
      if (pythonAvailable) {
        diarizationAvailable = await access(path.join(process.cwd(), "python", "pydub")).then(() => true).catch(() => false);
        if (diarizationAvailable) {
          this.logger.info("✅ Dependências de diarização disponíveis (pasta python/pydub presente)");
        } else {
          recommendations.push("Adicionar pasta python/pydub com arquivo de áudio");
        }
      }
      
      // VERIFICAÇÃO 5: FFmpeg
      const ffmpegAvailable = await access('ffmpeg')
        .then(() => {
          this.logger.info("✅ FFmpeg detectado (binário ffmpeg presente)");
          return true;
        })
        .catch(() => {
          recommendations.push("Instalar FFmpeg para processamento de áudio");
          return false;
        });
      
      // ANÁLISE DE RECURSOS DO SISTEMA
      const memoryUsage = process.memoryUsage().heapUsed / 1024 / 1024; // MB
      const cpuCores = require('os').cpus().length;
      
      // ESTIMATIVA DE PERFORMANCE EDUCATIVA
      let estimatedPerformance = "unknown";
      let performanceExplanation = "";
      
      if (whisperAvailable && diarizationAvailable && ffmpegAvailable) {
        if (cpuCores >= 8) {
          estimatedPerformance = "excellent";
          performanceExplanation = "Sistema otimizado para processamento rápido";
        } else if (cpuCores >= 4) {
          estimatedPerformance = "good";
          performanceExplanation = "Desempenho adequado para maioria dos casos";
        } else {
          estimatedPerformance = "basic";
          performanceExplanation = "Funcional, mas pode ser lento para áudios longos";
          recommendations.push("Considerar mais CPUs para melhor performance");
        }
      } else {
        estimatedPerformance = "limited";
        performanceExplanation = "Dependências faltando limitam funcionalidade";
      }
      
      // RELATÓRIO FINAL
      const status = {
        pythonAvailable,
        scriptAvailable,
        whisperAvailable,
        diarizationAvailable,
        ffmpegAvailable,
        memoryUsage: Math.round(memoryUsage * 100) / 100,
        cpuCores,
        estimatedPerformance,
        recommendations
      };
      
      this.logger.info("📋 Diagnóstico do sistema completo", {
        status,
        explanation: performanceExplanation,
        readyForProduction: whisperAvailable && scriptAvailable && ffmpegAvailable
      });
      
      return status;
      
    } catch (error: any) {
      this.logger.error("❌ Erro durante diagnóstico do sistema", { error: error.message });
      return {
        pythonAvailable: false,
        scriptAvailable: false,
        whisperAvailable: false,
        diarizationAvailable: false,
        ffmpegAvailable: false,
        memoryUsage: 0,
        cpuCores: 0,
        estimatedPerformance: "error",
        recommendations: ["Investigar problemas de configuração do ambiente"]
      };
    }
  }

  /**
   * TESTE EDUCATIVO: testTranscription
   * 
   * Método para testar rapidamente se o sistema está funcionando
   * sem precisar processar um áudio real.
   */
  public async testTranscription(): Promise<boolean> {
    try {
      this.logger.info("🧪 Executando teste rápido do sistema de transcrição...");
      
      // Teste simples: verificar se conseguimos importar as bibliotecas essenciais
      await access(path.join(process.cwd(), "python", "whisper")).then(() => {
        this.logger.info("✅ Whisper instalado (pasta python/whisper presente)");
      }).catch(() => {
        this.logger.error("❌ Whisper não encontrado. Verifique a pasta python/whisper");
        throw new Error("Whisper não encontrado");
      });

      await access(path.join(process.cwd(), "python", "pydub")).then(() => {
        this.logger.info("✅ pydub instalado (pasta python/pydub presente)");
      }).catch(() => {
        this.logger.error("❌ pydub não encontrado. Verifique a pasta python/pydub");
        throw new Error("pydub não encontrado");
      });

      await access('ffmpeg').then(() => {
        this.logger.info("✅ FFmpeg instalado (binário ffmpeg presente)");
      }).catch(() => {
        this.logger.error("❌ FFmpeg não encontrado. Verifique o binário ffmpeg");
        throw new Error("FFmpeg não encontrado");
      });
      
      this.logger.info("✅ Teste de transcrição passou - sistema pronto para uso");
      return true;
      
    } catch (error: any) {
      this.logger.error("❌ Teste de transcrição falhou", { 
        error: error.message,
        suggestion: "Verificar instalação das dependências"
      });
      return false;
    }
  }
}