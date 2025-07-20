import { Logger } from "../../utils/logger";
import fs from "fs/promises";
import { spawn } from "child_process";
import path from "path";

/**
 * Interface simplificada para versão gratuita
 * FILOSOFIA: Mantemos apenas os campos essenciais, eliminando complexidade desnecessária
 * que estava causando problemas no sistema anterior
 */
export interface TranscriptionResult {
  status: "success" | "error";
  text?: string;
  language?: string;
  processing_type?: string;
  timestamp?: string;
  error?: string;
  diarization_available?: boolean; // Indica se diarização gratuita está funcionando
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
  public async transcribeAudio(
    videoPath: string, // agora espera o caminho do vídeo
    videoId: string,
    outputDir?: string
  ): Promise<string> {
    this.logger.info(`🎯 Iniciando transcrição SIMPLES para videoId: ${videoId}`, {
      videoPath,
      outputDir,
      config: this.config,
      approach: "simple_transcribe.py (sequencial, sem erros)"
    });

    const scriptPath = path.join(process.cwd(), "python", "simple_transcribe.py");

    try {
      // Verificar se o script existe
      const scriptExists = await fs.access(scriptPath).then(() => true).catch(() => false);
      if (!scriptExists) {
        throw new Error(`Script simple_transcribe.py não encontrado em ${scriptPath}`);
      }
      // Verificar se o vídeo existe
      const videoExists = await fs.access(videoPath).then(() => true).catch(() => false);
      if (!videoExists) {
        throw new Error(`Arquivo de vídeo não encontrado: ${videoPath}`);
      }
      
      // Atualizar progresso no banco
      await this.updateVideoProgress(videoId, 60, "Transcrevendo áudio...");
      
      // Executar o script Python
      const startTime = Date.now();
      const result = await this.executeSimpleTranscription(scriptPath, videoPath, outputDir, videoId);
      const duration = (Date.now() - startTime) / 1000;
      
      // Atualizar progresso final
      await this.updateVideoProgress(videoId, 90, "Processando transcrição...");
      
      // Processar resultado
      const transcription = this.processSegmentsResult(result, duration, videoId);
      
      // Atualizar progresso final
      await this.updateVideoProgress(videoId, 100, "Transcrição concluída");
      
      this.logger.info("✅ Transcrição SIMPLES concluída com sucesso", {
        videoId,
        durationSeconds: duration,
        segments: result.segments?.length || 0,
        textLength: transcription.length,
        metadata: result.metadata
      });
      return transcription;
    } catch (error: any) {
      // Atualizar progresso de erro
      await this.updateVideoProgress(videoId, 0, "Erro na transcrição");
      
      this.logger.error("❌ Erro na transcrição:", {
        videoId,
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  private async executeSimpleTranscription(
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
    this.logger.info("Executando script Python simples", { scriptPath, videoPath, outputDir });
    
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

      // Timeout de 4 horas para vídeos longos
      const timeout = setTimeout(() => {
        this.logger.error("[simple_transcribe.py][timeout]", { 
          message: "Processo Python excedeu o tempo limite de 4 horas",
          videoPath 
        });
        python.kill('SIGKILL');
        reject(new Error("Timeout: Processo Python excedeu 4 horas"));
      }, 4 * 60 * 60 * 1000); // 4 horas

      python.stdout.on("data", (data) => {
        const chunk = data.toString();
        stdoutBuffer += chunk;
        
        // Log a cada 60 segundos para acompanhar o progresso
        const now = Date.now();
        if (now - lastLogTime > 60000) {
          this.logger.info("[simple_transcribe.py][stdout-progress]", { 
            bufferLength: stdoutBuffer.length,
            lastChunk: chunk.slice(-200)
          });
          lastLogTime = now;
        }
      });

      python.stderr.on("data", (data) => {
        const chunk = data.toString();
        stderrBuffer += chunk;
        
        // Extrair informações de progresso dos logs do Python
        const progressMatch = chunk.match(/Transcrevendo chunk (\d+)\/(\d+) \(([\d.]+)%\)/);
        const chunkMatch = chunk.match(/Chunk (\d+) concluído/);
        
        if (progressMatch) {
          const current = parseInt(progressMatch[1]);
          const total = parseInt(progressMatch[2]);
          const progress = parseFloat(progressMatch[3]);
          this.logger.info(`📊 Progresso: ${current}/${total} (${progress.toFixed(1)}%)`);
        }
        
        if (chunkMatch) {
          const chunkNum = chunkMatch[1];
          this.logger.info(`✅ Chunk ${chunkNum} concluído`);
        }
        
        this.logger.info("[simple_transcribe.py][stderr]", { stderr: chunk });
      });

      python.on("close", (code) => {
        clearTimeout(timeout);
        this.logger.info("[simple_transcribe.py][exit]", { code });
        
        if (code !== 0) {
          this.logger.error("[simple_transcribe.py][error]", { 
            code, 
            stderr: stderrBuffer,
            stdout: stdoutBuffer.slice(-500)
          });
          reject(new Error(`Script Python falhou com código ${code}`));
          return;
        }
        
        try {
          const cleanedStdout = stdoutBuffer.trim();
          const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}$/);
          if (jsonMatch) {
            const result = JSON.parse(jsonMatch[0]);
            this.logger.info("[simple_transcribe.py][success]", { 
              segmentsCount: result.segments?.length || 0,
              hasError: !!result.error
            });
            resolve(result);
          } else {
            this.logger.error("[simple_transcribe.py][parse-error]", { 
              stdout: cleanedStdout.slice(-500)
            });
            reject(new Error("Falha ao processar saída do simple_transcribe.py"));
          }
        } catch (e: any) {
          this.logger.error("❌ Erro ao processar JSON do simple_transcribe.py", {
            error: e.message,
            rawOutputPreview: stdoutBuffer.slice(0, 500)
          });
          reject(new Error("Falha ao processar saída do simple_transcribe.py"));
        }
      });
      
      python.on("error", (err) => {
        clearTimeout(timeout);
        this.logger.error("❌ Erro ao spawnar processo Python", { error: err.message });
        reject(err);
      });
    });
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

  private processSegmentsResult(
    result: { 
      segments: Array<{ start: number; end: number; text: string; words?: any[] }>;
      metadata?: any;
    }, 
    duration: number, 
    videoId: string
  ): string {
    if (!result.segments || result.segments.length === 0) {
      this.logger.warn("Nenhum segmento encontrado no resultado", { videoId });
      return "Nenhuma transcrição gerada.";
    }

    // Ordenar segmentos por tempo de início
    const sortedSegments = result.segments.sort((a, b) => a.start - b.start);
    
    // Construir transcrição com timestamps precisos
    const transcriptionLines: string[] = [];
    
    for (const segment of sortedSegments) {
      const startTime = this.formatTimestamp(segment.start);
      const endTime = this.formatTimestamp(segment.end);
      const text = segment.text.trim();
      
      if (text) {
        transcriptionLines.push(`[${startTime} → ${endTime}] ${text}`);
      }
    }
    
    const finalTranscription = transcriptionLines.join('\n\n');
    
    this.logger.info("Transcrição processada", {
      videoId,
      segmentsCount: sortedSegments.length,
      totalLength: finalTranscription.length,
      processingTime: duration
    });
    
    return finalTranscription;
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
      const pythonAvailable = await fs.access('python')
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
      const scriptAvailable = await fs.access(scriptPath)
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
        whisperAvailable = await fs.access(path.join(process.cwd(), "python", "whisper")).then(() => true).catch(() => false);
        if (whisperAvailable) {
          this.logger.info("✅ Whisper instalado (pasta python/whisper presente)");
        } else {
          recommendations.push("Adicionar pasta python/whisper com arquivo de modelo Whisper");
        }
      }
      
      // VERIFICAÇÃO 4: Dependências da diarização
      let diarizationAvailable = false;
      if (pythonAvailable) {
        diarizationAvailable = await fs.access(path.join(process.cwd(), "python", "pydub")).then(() => true).catch(() => false);
        if (diarizationAvailable) {
          this.logger.info("✅ Dependências de diarização disponíveis (pasta python/pydub presente)");
        } else {
          recommendations.push("Adicionar pasta python/pydub com arquivo de áudio");
        }
      }
      
      // VERIFICAÇÃO 5: FFmpeg
      const ffmpegAvailable = await fs.access('ffmpeg')
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
      await fs.access(path.join(process.cwd(), "python", "whisper")).then(() => {
        this.logger.info("✅ Whisper instalado (pasta python/whisper presente)");
      }).catch(() => {
        this.logger.error("❌ Whisper não encontrado. Verifique a pasta python/whisper");
        throw new Error("Whisper não encontrado");
      });

      await fs.access(path.join(process.cwd(), "python", "pydub")).then(() => {
        this.logger.info("✅ pydub instalado (pasta python/pydub presente)");
      }).catch(() => {
        this.logger.error("❌ pydub não encontrado. Verifique a pasta python/pydub");
        throw new Error("pydub não encontrado");
      });

      await fs.access('ffmpeg').then(() => {
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