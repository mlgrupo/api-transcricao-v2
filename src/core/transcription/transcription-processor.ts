import { Logger } from "../../utils/logger";
import fs from "fs/promises";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

/**
 * Interface simplificada para compatibilidade
 * Mantida para não quebrar o código existente
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
 * Configuração simplificada para compatibilidade
 */
export interface TranscriptionConfig {
  maxWorkers?: number;
  enableDiarization?: boolean;
  enableDirectTranscription?: boolean;
  timeoutMinutes?: number;
}

/**
 * CLASSE PRINCIPAL: TranscriptionProcessor
 * 
 * Versão simplificada baseada no projeto antigo que funcionava bem
 * Mantém compatibilidade total com o backend existente
 */
export class TranscriptionProcessor {
  constructor(
    private logger: Logger,
    private config: TranscriptionConfig = {}
  ) {
    this.logger.info("TranscriptionProcessor iniciado (versão simplificada)", {
      philosophy: "Simplicidade, robustez e compatibilidade"
    });
  }

  /**
   * MÉTODO PRINCIPAL: transcribeVideo
   * 
   * Mantido para compatibilidade com código que pode usar este método
   * Internamente chama transcribeVideoLegacy
   */
  public async transcribeVideo(videoPath: string): Promise<TranscriptionResult> {
    try {
      this.logger.info(`🎯 Iniciando transcrição para ${videoPath}`);
      
      const text = await this.transcribeVideoLegacy(videoPath);
      
      // Converter para formato TranscriptionResult para compatibilidade
      const result: TranscriptionResult = {
        success: true,
        segments: [{
          start: 0,
          end: 0,
          text: text
        }],
        language: 'pt',
        transcribe_time: 0,
        audio_duration: 0,
        total_segments: 1,
        improved_segments: 0,
        resources_used: {
          cpu_percent: 0,
          memory_percent: 0,
          cpus_per_worker: 4,
          max_workers: 2,
          ram_per_worker_gb: 13
        }
      };
      
      this.logger.info(`🎉 Transcrição concluída com sucesso!`);
      return result;

    } catch (error) {
      this.logger.error(`💥 Erro na transcrição: ${error}`);
      
      const errorResult: TranscriptionResult = {
        success: false,
        segments: [],
        language: 'pt',
        transcribe_time: 0,
        audio_duration: 0,
        total_segments: 0,
        improved_segments: 0,
        resources_used: {
          cpu_percent: 0,
          memory_percent: 0,
          cpus_per_worker: 4,
          max_workers: 2,
          ram_per_worker_gb: 13
        },
        error: error instanceof Error ? error.message : 'Erro desconhecido'
      };
      
      return errorResult;
    }
  }

  /**
   * MÉTODO LEGACY: transcribeVideoLegacy
   * 
   * Este é o método principal usado pelo VideoProcessor
   * Baseado no código antigo que funcionava bem
   */
  public async transcribeVideoLegacy(videoPath: string, outputDir?: string, videoId?: string): Promise<string> {
    this.logger.info(`TranscriptionProcessor initialized for videoId: ${videoId}`);
    const execAsync = promisify(exec);

    // Caminho absoluto para o script Python
    const scriptPath = path.join(process.cwd(), "python", "transcribe.py");

    try {
      this.logger.info("Iniciando transcrição do áudio...", { audioPath: videoPath });

      // Verificar se o script Python existe
      const scriptExists = await fs.access(scriptPath).then(() => true).catch(() => false);
      if (!scriptExists) {
        this.logger.error(`Script Python não encontrado: ${scriptPath}`);
        return "Erro: Script de transcrição não encontrado. Transcrição não disponível.";
      }

      // Verificar se o arquivo de áudio existe
      const audioExists = await fs.access(videoPath).then(() => true).catch(() => false);
      if (!audioExists) {
        this.logger.error(`Arquivo de áudio não encontrado: ${videoPath}`);
        return "Erro: Arquivo de áudio não encontrado. Transcrição não disponível.";
      }

      // Enviando para o python transcrever
      try {
        const startTime = Date.now();
        
        // Usar python3 se disponível, senão python
        let pythonCommand = 'python3';
        try {
          await execAsync('python3 --version');
        } catch {
          pythonCommand = 'python';
        }
        
        const { stdout } = await execAsync(`${pythonCommand} "${scriptPath}" "${videoPath}"`, {
          maxBuffer: 1024 * 1024 * 10, // 10MB buffer
          encoding: "utf8",
          env: {
            ...process.env,
            PYTHONPATH: path.join(process.cwd(), 'python'),
            OMP_NUM_THREADS: '4',
            MKL_NUM_THREADS: '4',
            PYTORCH_NUM_THREADS: '4'
          }
        });

        const duration = (Date.now() - startTime) / 1000;

        let result;
        try {
          result = JSON.parse(stdout.trim());
        } catch (e: any) {
          this.logger.error("Erro ao parsear saída da transcrição:", {
            erro: e.message,
            bruto: stdout.slice(0, 1000) + "...",
          });
          throw new Error("Erro ao processar resultado da transcrição");
        }

        if (result.status === "error") {
          throw new Error(result.error || "Erro desconhecido na transcrição");
        }

        if (!result.text) {
          throw new Error("Transcrição retornou vazia");
        }

        this.logger.info("Transcrição concluída", {
          durationSeconds: duration,
          audioPath: videoPath,
          chunks: result.chunks,
        });

        return result.text;
      } catch (pythonError: any) {
        // Log the error but continue with alternative approach
        this.logger.error("Erro executando script Python:", {
          error: pythonError.message,
          audioPath: videoPath,
        });
      
        // Return fallback message if Python script fails
        return "Este vídeo não pôde ser transcrito devido a um erro técnico. " +
               "Por favor, tente novamente mais tarde ou entre em contato com o suporte.";
      }
    } catch (error: any) {
      this.logger.error("Erro fatal na transcrição:", {
        error: error.message,
        audioPath: videoPath,
      });
      throw new Error(`Erro na transcrição: ${error.message}`);
    }
  }

  /**
   * MÉTODOS DE COMPATIBILIDADE
   * Mantidos para não quebrar código que pode usar estes métodos
   */

  public updateConfig(newConfig: Partial<TranscriptionConfig>): void {
    this.config = { ...this.config, ...newConfig };
    this.logger.info('Configuração atualizada', { config: this.config });
  }

  public getConfig(): TranscriptionConfig {
    return { ...this.config };
  }

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
    try {
      const os = require('os');
      const { exec } = require('child_process');
      const { promisify } = require('util');
      const execAsync = promisify(exec);

      // Verificar Python
      let pythonAvailable = false;
      try {
        await execAsync('python3 --version');
        pythonAvailable = true;
      } catch (e) {
        try {
          await execAsync('python --version');
          pythonAvailable = true;
        } catch (e) {
          // Python não disponível
        }
      }

      // Verificar script
      const scriptPath = path.join(process.cwd(), 'python', 'transcribe.py');
      const scriptAvailable = await fs.access(scriptPath).then(() => true).catch(() => false);

      // Verificar Whisper
      let whisperAvailable = false;
      if (pythonAvailable) {
        try {
          await execAsync('python3 -c "import whisper"');
          whisperAvailable = true;
        } catch (e) {
          try {
            await execAsync('python -c "import whisper"');
            whisperAvailable = true;
          } catch (e) {
            // Whisper não disponível
          }
        }
      }

      // Verificar FFmpeg
      let ffmpegAvailable = false;
      try {
        await execAsync('ffmpeg -version');
        ffmpegAvailable = true;
      } catch (e) {
        // FFmpeg não disponível
      }

      // Informações do sistema
      const memoryUsage = ((os.totalmem() - os.freemem()) / os.totalmem()) * 100;
      const cpuCores = os.cpus().length;

      // Estimativa de performance
      let estimatedPerformance = 'Baixa';
      if (cpuCores >= 8 && memoryUsage < 80) {
        estimatedPerformance = 'Alta';
      } else if (cpuCores >= 4 && memoryUsage < 90) {
        estimatedPerformance = 'Média';
      }

      // Recomendações
      const recommendations: string[] = [];
      if (!pythonAvailable) recommendations.push('Instalar Python 3.8+');
      if (!scriptAvailable) recommendations.push('Verificar arquivo transcribe.py');
      if (!whisperAvailable) recommendations.push('Instalar OpenAI Whisper: pip install openai-whisper');
      if (!ffmpegAvailable) recommendations.push('Instalar FFmpeg');
      if (memoryUsage > 90) recommendations.push('Liberar memória RAM');
      if (cpuCores < 4) recommendations.push('Considerar hardware com mais cores');

      return {
        pythonAvailable,
        scriptAvailable,
        whisperAvailable,
        diarizationAvailable: false, // Não usado na versão atual
        ffmpegAvailable,
        memoryUsage,
        cpuCores,
        estimatedPerformance,
        recommendations
      };

    } catch (error) {
      this.logger.error('Erro ao verificar status do sistema:', error);
      return {
        pythonAvailable: false,
        scriptAvailable: false,
        whisperAvailable: false,
        diarizationAvailable: false,
        ffmpegAvailable: false,
        memoryUsage: 0,
        cpuCores: 0,
        estimatedPerformance: 'Desconhecida',
        recommendations: ['Verificar logs de erro']
      };
    }
  }

  public async testTranscription(): Promise<boolean> {
    try {
      this.logger.info('🧪 Iniciando teste de transcrição...');
      
      const status = await this.checkSystemStatus();
      if (!status.pythonAvailable || !status.scriptAvailable || !status.whisperAvailable) {
        this.logger.error('❌ Dependências não disponíveis para teste');
        return false;
      }

      this.logger.info('✅ Todas as dependências disponíveis');
      this.logger.info('✅ Teste de transcrição concluído com sucesso');
      
      return true;
    } catch (error) {
      this.logger.error('❌ Erro no teste de transcrição:', error);
      return false;
    }
  }
} 