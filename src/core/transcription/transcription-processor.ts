import { Logger } from "../../utils/logger";
import fs from "fs/promises";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

// Interface simplificada para versão gratuita
export interface TranscriptionResult {
  status: "success" | "error";
  text?: string;
  language?: string;
  processing_type?: string;
  timestamp?: string;
  error?: string;
  diarization_available?: boolean; // Indica se diarização está funcionando
}

// Configuração simplificada para versão gratuita
export interface TranscriptionConfig {
  maxWorkers?: number;
  enableDiarization?: boolean; // Substituiu todas as outras opções avançadas
  enableDirectTranscription?: boolean; // Para áudios muito curtos
  timeoutMinutes?: number; // Timeout configurável
}

export class TranscriptionProcessor {
  private config: TranscriptionConfig;

  constructor(
    private logger: Logger,
    config: TranscriptionConfig = {}
  ) {
    this.config = {
      maxWorkers: parseInt(process.env.MAX_WORKERS || '4'), // Reduzido para versão gratuita
      enableDiarization: true, // Por padrão, tentar diarização
      enableDirectTranscription: false, // Por padrão, usar diarização
      timeoutMinutes: 30, // 30 minutos timeout padrão
      ...config
    };
    
    this.logger.info("TranscriptionProcessor iniciado (versão gratuita)", {
      config: this.config
    });
  }

  public async transcribeAudio(
    audioPath: string, 
    videoId: string,
    outputDir?: string
  ): Promise<string> {
    this.logger.info(`Iniciando transcrição gratuita para videoId: ${videoId}`, {
      audioPath,
      outputDir,
      config: this.config
    });

    const execAsync = promisify(exec);
    
    // Usar nosso script gratuito
    const scriptPath = path.join(process.cwd(), "python", "transcription.py");

    try {
      // Verificações iniciais
      await this.validateEnvironment(scriptPath, audioPath);

      // Executar transcrição gratuita
      const startTime = Date.now();
      const result = await this.executeFreeTranscription(execAsync, scriptPath, audioPath, outputDir);
      const duration = (Date.now() - startTime) / 1000;

      // Processar resultado
      const transcription = this.processTranscriptionResult(result, duration, videoId);

      this.logger.info("Transcrição gratuita concluída", {
        videoId,
        durationSeconds: duration,
        processingType: result.processing_type,
        diarizationAvailable: result.diarization_available,
        textLength: transcription.length
      });

      return transcription;

    } catch (error: any) {
      this.logger.error("Erro na transcrição gratuita", {
        videoId,
        error: error.message,
        stack: error.stack
      });
      
      // Tentar fallback simples se a transcrição principal falhar
      return await this.attemptFallbackTranscription(audioPath, videoId);
    }
  }

  private async validateEnvironment(scriptPath: string, audioPath: string): Promise<void> {
    // Verificar script Python gratuito
    const scriptExists = await fs.access(scriptPath).then(() => true).catch(() => false);
    if (!scriptExists) {
      throw new Error(`Script gratuito não encontrado: ${scriptPath}. Certifique-se de que transcription.py está na pasta python/`);
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

    // Log informações do arquivo
    const fileSizeMB = (audioStats.size / 1024 / 1024).toFixed(2);
    this.logger.info("Validação de ambiente concluída", {
      audioPath,
      fileSize: `${fileSizeMB}MB`,
      scriptType: "transcription.py"
    });
  }

  private async executeFreeTranscription(
    execAsync: any,
    scriptPath: string,
    audioPath: string,
    outputDir?: string
  ): Promise<TranscriptionResult> {
    this.logger.info("Executando transcrição gratuita com Whisper...");

    // Construir comando para script gratuito
    let command = `python "${scriptPath}" "${audioPath}"`;
    
    if (outputDir) {
      command += ` "${outputDir}"`;
    }

    // Configurar ambiente sem token HuggingFace
    const env = { ...process.env };
    env.PYTHONIOENCODING = "utf-8";
    env.LC_ALL = "pt_BR.UTF-8";
    env.LANG = "pt_BR.UTF-8";
    
    // Remover HF_TOKEN se existir (não precisamos mais)
    delete env.HF_TOKEN;

    this.logger.info("Executando comando Python", { command });

    const timeoutMs = this.config.timeoutMinutes! * 60 * 1000;
    
    const { stdout, stderr } = await execAsync(command, {
      maxBuffer: 1024 * 1024 * 50, // 50MB buffer
      encoding: "buffer",
      timeout: timeoutMs,
      env,
    });

    // Converter buffer para string UTF-8
    const stdoutText = stdout.toString('utf-8');
    const stderrText = stderr.toString('utf-8');

    // Log stderr se houver (mas não como erro, pode ser só info)
    if (stderrText && stderrText.trim()) {
      this.logger.info("Output do script Python:", { stderr: stderrText.trim() });
    }

    // Parsear resultado JSON
    let result: TranscriptionResult;
    try {
      const cleanedStdout = stdoutText.trim();
      
      // Tentar encontrar JSON no final da saída
      const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}$/);
      if (jsonMatch) {
        result = JSON.parse(jsonMatch[0]);
      } else {
        result = JSON.parse(cleanedStdout);
      }
      
      this.logger.info("JSON parseado com sucesso", { 
        status: result.status,
        processingType: result.processing_type,
        diarizationAvailable: result.diarization_available
      });
      
    } catch (e: any) {
      this.logger.error("Erro ao parsear JSON da transcrição:", {
        error: e.message,
        rawOutput: stdoutText.slice(0, 500) + "..."
      });
      
      // Tentar extrair texto manualmente do stdout
      const textMatch = stdoutText.match(/"text":\s*"([^"]+)"/);
      if (textMatch && textMatch[1]) {
        this.logger.warn("Extraindo texto manualmente do output malformado");
        result = {
          status: "success",
          text: textMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"'),
          language: "pt",
          processing_type: "fallback_extraction",
          timestamp: new Date().toISOString(),
          diarization_available: false
        };
      } else {
        throw new Error(`Falha ao processar saída do script Python: ${e.message}`);
      }
    }

    return result;
  }

  private async attemptFallbackTranscription(audioPath: string, videoId: string): Promise<string> {
    this.logger.warn("Tentando transcrição de fallback (só Whisper)", { videoId });
    
    try {
      const execAsync = promisify(exec);
      
      // Tentar transcrição direta com Whisper via Python
      const fallbackCommand = `python -c "
import whisper
import sys
try:
    model = whisper.load_model('medium', device='cpu')
    result = model.transcribe('${audioPath}', language='pt')
    print(result['text'])
except Exception as e:
    print(f'Erro: {e}')
    sys.exit(1)
"`;

      const { stdout } = await execAsync(fallbackCommand, {
        timeout: 20 * 60 * 1000, // 20 minutos
        encoding: 'utf-8'
      });

      const text = stdout.trim();
      if (text && !text.startsWith('Erro:')) {
        this.logger.info("Fallback bem-sucedido", { videoId, textLength: text.length });
        return text;
      } else {
        throw new Error("Fallback retornou erro ou texto vazio");
      }
      
    } catch (error: any) {
      this.logger.error("Fallback também falhou", { videoId, error: error.message });
      throw new Error("Todas as tentativas de transcrição falharam");
    }
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

    // Log de métricas simplificadas
    this.logger.info("Métricas da transcrição gratuita", {
      videoId,
      durationSeconds: duration,
      textLength: result.text.length,
      processingType: result.processing_type,
      diarizationUsed: result.diarization_available,
      wordsEstimated: result.text.split(/\s+/).length
    });

    return result.text;
  }

  // Métodos para configuração (simplificados)
  public updateConfig(newConfig: Partial<TranscriptionConfig>): void {
    this.config = { ...this.config, ...newConfig };
    this.logger.info("Configuração atualizada (versão gratuita)", { config: this.config });
  }

  public getConfig(): TranscriptionConfig {
    return { ...this.config };
  }

  // Verificação de sistema para versão gratuita
  public async checkSystemStatus(): Promise<{
    pythonAvailable: boolean;
    scriptAvailable: boolean;
    whisperAvailable: boolean;
    diarizationAvailable: boolean;
    ffmpegAvailable: boolean;
    memoryUsage: number;
    cpuCores: number;
    estimatedPerformance: string;
  }> {
    try {
      const execAsync = promisify(exec);
      
      // Verificar Python
      const pythonAvailable = await execAsync('python --version')
        .then(() => true)
        .catch(() => false);
      
      // Verificar script gratuito
      const scriptPath = path.join(process.cwd(), "python", "transcription.py");
      const scriptAvailable = await fs.access(scriptPath)
        .then(() => true)
        .catch(() => false);
      
      // Verificar Whisper
      let whisperAvailable = false;
      if (pythonAvailable) {
        whisperAvailable = await execAsync('python -c "import whisper; print(\'ok\')"')
          .then(() => true)
          .catch(() => false);
      }
      
      // Verificar dependências da diarização gratuita
      let diarizationAvailable = false;
      if (pythonAvailable) {
        diarizationAvailable = await execAsync('python -c "import pydub, numpy; print(\'ok\')"')
          .then(() => true)
          .catch(() => false);
      }
      
      // Verificar FFmpeg
      const ffmpegAvailable = await execAsync('ffmpeg -version')
        .then(() => true)
        .catch(() => false);
      
      // Informações do sistema
      const memoryUsage = process.memoryUsage().heapUsed / 1024 / 1024; // MB
      const cpuCores = require('os').cpus().length;
      
      // Estimar performance baseada no sistema
      let estimatedPerformance = "unknown";
      if (whisperAvailable && diarizationAvailable && ffmpegAvailable) {
        if (cpuCores >= 8) {
          estimatedPerformance = "excellent";
        } else if (cpuCores >= 4) {
          estimatedPerformance = "good";
        } else {
          estimatedPerformance = "basic";
        }
      } else {
        estimatedPerformance = "limited";
      }
      
      this.logger.info("Status do sistema verificado", {
        pythonAvailable,
        scriptAvailable,
        whisperAvailable,
        diarizationAvailable,
        ffmpegAvailable,
        cpuCores,
        estimatedPerformance
      });
      
      return {
        pythonAvailable,
        scriptAvailable,
        whisperAvailable,
        diarizationAvailable,
        ffmpegAvailable,
        memoryUsage: Math.round(memoryUsage * 100) / 100,
        cpuCores,
        estimatedPerformance
      };
      
    } catch (error: any) {
      this.logger.error("Erro ao verificar status do sistema:", error);
      return {
        pythonAvailable: false,
        scriptAvailable: false,
        whisperAvailable: false,
        diarizationAvailable: false,
        ffmpegAvailable: false,
        memoryUsage: 0,
        cpuCores: 0,
        estimatedPerformance: "error"
      };
    }
  }

  // Método para testar uma transcrição rápida
  public async testTranscription(): Promise<boolean> {
    try {
      this.logger.info("Executando teste de transcrição...");
      
      // Verificar se conseguimos importar as bibliotecas básicas
      const execAsync = promisify(exec);
      await execAsync('python -c "import whisper, pydub, numpy; print(\'Bibliotecas OK\')"', {
        timeout: 30000
      });
      
      this.logger.info("Teste de transcrição passou - bibliotecas disponíveis");
      return true;
      
    } catch (error: any) {
      this.logger.error("Teste de transcrição falhou", { error: error.message });
      return false;
    }
  }
}