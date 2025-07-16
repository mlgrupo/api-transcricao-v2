import { Logger } from "../../utils/logger";
import fs from "fs/promises";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

export interface TranscriptionResult {
  status: "success" | "error";
  text?: string;
  language?: string;
  processing_type?: string;
  timestamp?: string;
  error?: string;
  chunks?: number;
  context?: string;
  emotions?: Record<string, number>;
  metadata?: {
    duration: number;
    audio_quality: string;
    noise_reduced: boolean;
    silence_removed: boolean;
    volume_normalized: boolean;
  };
}

export interface TranscriptionConfig {
  maxWorkers?: number;
  chunkDurationMs?: number;
  maxMemoryChunks?: number;
  enableNoiseReduction?: boolean;
  enableSilenceRemoval?: boolean;
  enableVolumeNormalization?: boolean;
  enableContextDetection?: boolean;
  enableSpellCheck?: boolean;
  enableEmotionDetection?: boolean;
}

export class TranscriptionProcessor {
  private config: TranscriptionConfig;

  constructor(
    private logger: Logger,
    config: TranscriptionConfig = {}
  ) {
    this.config = {
      maxWorkers: 4, // Ajustado para CPU-only (não sobrecarregar)
      chunkDurationMs: 3 * 60 * 1000, // Reduzido de 5 para 3 minutos
      maxMemoryChunks: 5, // Aumentado de 3 para 5
      enableNoiseReduction: true,
      enableSilenceRemoval: true,
      enableVolumeNormalization: true,
      enableContextDetection: true,
      enableSpellCheck: false, // Desabilitado por padrão para melhor performance
      enableEmotionDetection: false, // Desabilitado por padrão para melhor performance
      ...config
    };
  }

  public async transcribeAudio(
    audioPath: string, 
    videoId: string,
    outputDir?: string
  ): Promise<string> {
    this.logger.info(`TranscriptionProcessor inicializado para videoId: ${videoId}`, {
      audioPath,
      outputDir,
      config: this.config
    });

    const execAsync = promisify(exec);
    const scriptPath = path.join(process.cwd(), "python", "transcribe.py");

    try {
      // Verificações iniciais
      await this.validateEnvironment(scriptPath, audioPath);

      // Executar transcrição avançada
      const startTime = Date.now();
      const result = await this.executeAdvancedTranscription(execAsync, scriptPath, audioPath, outputDir);
      const duration = (Date.now() - startTime) / 1000;

      // Processar resultado
      const transcription = this.processTranscriptionResult(result, duration, videoId);

      this.logger.info("Texto recebido do Python (pré-banco)", { videoId, transcription });

      this.logger.info("Transcrição avançada concluída", {
        videoId,
        durationSeconds: duration,
        processingType: result.processing_type,
        context: result.context,
        chunks: result.chunks,
        emotions: result.emotions,
        metadata: result.metadata
      });

      return transcription;

    } catch (error: any) {
      this.logger.error("Erro na transcrição avançada", {
        videoId,
        error: error.message,
        stack: error.stack
      });
      // Não tentar fallback, apenas lançar o erro
      throw error;
    }
  }

  private async validateEnvironment(scriptPath: string, audioPath: string): Promise<void> {
    // Verificar script Python
    const scriptExists = await fs.access(scriptPath).then(() => true).catch(() => false);
    if (!scriptExists) {
      throw new Error(`Script Python não encontrado: ${scriptPath}`);
    }

    // Verificar arquivo de áudio
    const audioExists = await fs.access(audioPath).then(() => true).catch(() => false);
    if (!audioExists) {
      throw new Error(`Arquivo de áudio não encontrado: ${audioPath}`);
    }

    // Verificar tamanho do arquivo
    const audioStats = await fs.stat(audioPath);
    if (audioStats.size === 0) {
      throw new Error("Arquivo de áudio está vazio");
    }

    this.logger.info("Verificações de ambiente concluídas", {
      audioPath,
      fileSize: `${(audioStats.size / 1024 / 1024).toFixed(2)}MB`
    });
  }

  private async executeAdvancedTranscription(
    execAsync: any,
    scriptPath: string,
    audioPath: string,
    outputDir?: string
  ): Promise<TranscriptionResult> {
    this.logger.info("Executando transcrição avançada...");

    // Construir comando com parâmetros avançados
    let command = `python "${scriptPath}" "${audioPath}"`;
    
    if (outputDir) {
      command += ` "${outputDir}"`;
    }

    // Adicionar variável de ambiente HF_TOKEN e configurar UTF-8
    const env = { ...process.env };
    env.HF_TOKEN = process.env.HF_TOKEN || "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";
    env.PYTHONIOENCODING = "utf-8";
    env.LC_ALL = "pt_BR.UTF-8";
    env.LANG = "pt_BR.UTF-8";

    const { stdout, stderr } = await execAsync(command, {
      maxBuffer: 1024 * 1024 * 50, // 50MB buffer
      encoding: "buffer", // Usar buffer para controle manual do encoding
      timeout: 30 * 60 * 1000, // 30 minutos timeout (reduzido de 45 minutos)
      env,
    });

    // Converter buffer para string UTF-8 explicitamente
    const stdoutText = stdout.toString('utf-8');
    const stderrText = stderr.toString('utf-8');

    // Log stderr se houver
    if (stderrText && stderrText.trim()) {
      this.logger.warn("Stderr do script Python:", { stderr: stderrText.trim() });
    }

    // Parsear resultado - tentar encontrar JSON válido
    let result: TranscriptionResult;
    try {
      // Limpar stdout e tentar encontrar JSON
      const cleanedStdout = stdoutText.trim();
      
      // Tentar encontrar o JSON no final da string
      const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}$/);
      if (jsonMatch) {
        result = JSON.parse(jsonMatch[0]);
      } else {
        // Se não encontrar JSON no final, tentar parsear toda a string
        result = JSON.parse(cleanedStdout);
      }
    } catch (e: any) {
      this.logger.error("Erro ao parsear resultado da transcrição:", {
        error: e.message,
        raw: stdoutText.slice(0, 1000) + "..."
      });
      
      // Tentar extrair texto mesmo que o JSON esteja malformado
      const textMatch = stdoutText.match(/"text":\s*"([^"]+)"/);
      if (textMatch && textMatch[1]) {
        this.logger.warn("Extraindo texto do resultado malformado");
        result = {
          status: "success",
          text: textMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"'),
          language: "pt",
          processing_type: "optimized",
          timestamp: new Date().toISOString()
        };
      } else {
        throw new Error("Erro ao processar resultado da transcrição");
      }
    }

    return result;
  }

  private processTranscriptionResult(
    result: TranscriptionResult, 
    duration: number, 
    videoId: string
  ): string {
    if (result.status === "error") {
      throw new Error(result.error || "Erro desconhecido na transcrição");
    }

    if (!result.text || !result.text.trim()) {
      throw new Error("Transcrição retornou texto vazio");
    }

    // Log de métricas avançadas
    this.logger.info("Métricas da transcrição", {
      videoId,
      durationSeconds: duration,
      textLength: result.text.length,
      processingType: result.processing_type,
      context: result.context,
      chunks: result.chunks,
      emotions: result.emotions,
      metadata: result.metadata
    });

    return result.text;
  }

  // Métodos para configuração dinâmica
  public updateConfig(newConfig: Partial<TranscriptionConfig>): void {
    this.config = { ...this.config, ...newConfig };
    this.logger.info("Configuração de transcrição atualizada", { config: this.config });
  }

  public getConfig(): TranscriptionConfig {
    return { ...this.config };
  }

  // Método para verificar status do sistema
  public async checkSystemStatus(): Promise<{
    pythonAvailable: boolean;
    scriptAvailable: boolean;
    whisperAvailable: boolean;
    dependenciesAvailable: boolean;
    memoryUsage: number;
    cpuCores: number;
  }> {
    try {
      const execAsync = promisify(exec);
      
      // Verificar Python
      const pythonAvailable = await execAsync('python --version')
        .then(() => true)
        .catch(() => false);
      
      // Verificar script
      const scriptPath = path.join(process.cwd(), "python", "transcribe.py");
      const scriptAvailable = await fs.access(scriptPath)
        .then(() => true)
        .catch(() => false);
      
      // Verificar Whisper
      let whisperAvailable = false;
      if (pythonAvailable) {
        whisperAvailable = await execAsync('python -c "import whisper"')
          .then(() => true)
          .catch(() => false);
      }
      
      // Verificar dependências adicionais
      let dependenciesAvailable = false;
      if (pythonAvailable) {
        dependenciesAvailable = await execAsync('python -c "import noisereduce, webrtcvad, librosa"')
          .then(() => true)
          .catch(() => false);
      }
      
      // Informações do sistema
      const memoryUsage = process.memoryUsage().heapUsed / 1024 / 1024; // MB
      const cpuCores = require('os').cpus().length;
      
      return {
        pythonAvailable,
        scriptAvailable,
        whisperAvailable,
        dependenciesAvailable,
        memoryUsage: Math.round(memoryUsage * 100) / 100,
        cpuCores
      };
      
    } catch (error: any) {
      this.logger.error("Erro ao verificar status do sistema:", error);
      return {
        pythonAvailable: false,
        scriptAvailable: false,
        whisperAvailable: false,
        dependenciesAvailable: false,
        memoryUsage: 0,
        cpuCores: 0
      };
    }
  }
}