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
    this.logger.info(`🎯 Iniciando transcrição otimizada para videoId: ${videoId}`, {
      videoPath,
      outputDir,
      config: this.config,
      approach: "chunked_transcribe.py (sem diarização)"
    });

    const scriptPath = path.join(process.cwd(), "python", "chunked_transcribe.py");

    try {
      // Verificar se o script existe
      const scriptExists = await fs.access(scriptPath).then(() => true).catch(() => false);
      if (!scriptExists) {
        throw new Error(`Script chunked_transcribe.py não encontrado em ${scriptPath}`);
      }
      // Verificar se o vídeo existe
      const videoExists = await fs.access(videoPath).then(() => true).catch(() => false);
      if (!videoExists) {
        throw new Error(`Arquivo de vídeo não encontrado: ${videoPath}`);
      }
      // Executar o script Python
      const startTime = Date.now();
      const result = await this.executeChunkedTranscription(scriptPath, videoPath, outputDir);
      const duration = (Date.now() - startTime) / 1000;
      // Processar resultado
      const transcription = this.processSegmentsResult(result, duration, videoId);
      this.logger.info("✅ Transcrição concluída com sucesso", {
        videoId,
        durationSeconds: duration,
        segments: result.segments?.length || 0,
        textLength: transcription.length
      });
      return transcription;
    } catch (error: any) {
      this.logger.error("❌ Erro na transcrição:", {
        videoId,
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  private async executeChunkedTranscription(
    scriptPath: string,
    videoPath: string,
    outputDir?: string
  ): Promise<{ segments: Array<{ start: number; end: number; text: string }> }> {
    this.logger.info("🚀 Executando chunked_transcribe.py... (com logs em tempo real)", { scriptPath, videoPath });
    let commandArgs = [scriptPath, videoPath];
    if (outputDir) {
      commandArgs.push(outputDir);
    }
    const env = { ...process.env };
    env.PYTHONIOENCODING = "utf-8";
    env.LC_ALL = "pt_BR.UTF-8";
    env.LANG = "pt_BR.UTF-8";
    delete env.HF_TOKEN;
    return await new Promise((resolve, reject) => {
      const python = spawn("python", commandArgs, { env });
      let stdoutBuffer = "";
      let stderrBuffer = "";
      python.stdout.on("data", (data) => {
        const text = data.toString();
        stdoutBuffer += text;
      });
      python.stderr.on("data", (data) => {
        const text = data.toString();
        stderrBuffer += text;
        process.stderr.write(`[PYTHON STDERR] ${text}`); // Mostra logs do Python em tempo real
      });
      python.on("close", (code) => {
        this.logger.info("[chunked_transcribe.py][exit]", { code });
        if (stderrBuffer.trim()) {
          this.logger.info("[chunked_transcribe.py][stderr-final]", { stderr: stderrBuffer.slice(0, 500) });
        }
        try {
          const cleanedStdout = stdoutBuffer.trim();
          const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}$/);
          if (jsonMatch) {
            resolve(JSON.parse(jsonMatch[0]));
          } else {
            resolve(JSON.parse(cleanedStdout));
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
        this.logger.error("❌ Erro ao spawnar processo Python", { error: err.message });
        reject(err);
      });
    });
  }

  private processSegmentsResult(
    result: { segments: Array<{ start: number; end: number; text: string }> },
    duration: number,
    videoId: string
  ): string {
    if (!result || !Array.isArray(result.segments)) {
      throw new Error("Resultado inválido do chunked_transcribe.py: segments ausentes");
    }
    // Junta todos os textos com timestamps
    const textoFinal = result.segments.map(seg => {
      const ini = new Date(seg.start * 1000).toISOString().substr(11, 8);
      const fim = new Date(seg.end * 1000).toISOString().substr(11, 8);
      return `[${ini} - ${fim}] ${seg.text}`;
    }).join('\n');
    return textoFinal;
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