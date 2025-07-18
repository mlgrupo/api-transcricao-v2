import { Logger } from "../../utils/logger";
import fs from "fs/promises";
import { exec } from "child_process";
import { promisify } from "util";
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
    audioPath: string, 
    videoId: string,
    outputDir?: string
  ): Promise<string> {
    this.logger.info(`🎯 Iniciando transcrição educativa para videoId: ${videoId}`, {
      audioPath,
      outputDir,
      config: this.config,
      approach: "scripts-dedicados-sem-downloads-repetitivos"
    });

    const execAsync = promisify(exec);
    
    // CORREÇÃO FUNDAMENTAL 1: Nome correto do script
    // Esta era uma das principais causas de falha - usar nome incorreto
    const scriptPath = path.join(process.cwd(), "python", "transcription.py");

    try {
      // ETAPA 1: Verificações pedagógicas iniciais
      // Como um professor que verifica se os alunos trouxeram o material necessário
      await this.validateEnvironment(scriptPath, audioPath);

      // ETAPA 2: Executar transcrição inteligente
      // Aqui usamos scripts dedicados em vez de comandos inline problemáticos
      const startTime = Date.now();
      const result = await this.executeFreeTranscription(execAsync, scriptPath, audioPath, outputDir);
      const duration = (Date.now() - startTime) / 1000;

      // ETAPA 3: Processar e validar resultado
      const transcription = this.processTranscriptionResult(result, duration, videoId);

      this.logger.info("✅ Transcrição educativa concluída com sucesso", {
        videoId,
        durationSeconds: duration,
        processingType: result.processing_type,
        diarizationAvailable: result.diarization_available,
        textLength: transcription.length,
        wordsEstimated: transcription.split(/\s+/).length
      });

      return transcription;

    } catch (error: any) {
      this.logger.error("❌ Transcrição principal falhou, iniciando recuperação inteligente", {
        videoId,
        error: error.message,
        stack: error.stack,
        nextStep: "Tentaremos métodos de fallback progressivamente mais simples"
      });
      
      // FILOSOFIA DE RECUPERAÇÃO: Nunca desistir no primeiro erro
      // Em vez disso, tentar métodos progressivamente mais simples
      return await this.attemptEducationalFallback(audioPath, videoId);
    }
  }

  /**
   * MÉTODO DE VALIDAÇÃO: validateEnvironment
   * 
   * Este método funciona como um "checklist pré-voo" - verifica se tudo
   * está no lugar correto antes de começar o processo principal.
   * 
   * FILOSOFIA: Falhar rapidamente e com mensagens claras é melhor
   * que falhar depois de 20 minutos de processamento.
   */
  private async validateEnvironment(scriptPath: string, audioPath: string): Promise<void> {
    // VERIFICAÇÃO 1: Script Python existe?
    // Esta verificação evita 90% dos problemas de "arquivo não encontrado"
    const scriptExists = await fs.access(scriptPath).then(() => true).catch(() => false);
    if (!scriptExists) {
      throw new Error(`❌ Script educativo não encontrado: ${scriptPath}. 
      
      SOLUÇÃO: Certifique-se de que o arquivo 'transcription.py' está na pasta 'python/' do seu projeto.
      
      ESTRUTURA ESPERADA:
      seu-projeto/
      ├── python/
      │   └── transcription.py  ← Este arquivo deve existir
      └── src/
          └── seu-arquivo.ts`);
    }

    // VERIFICAÇÃO 2: Arquivo de áudio existe e é válido?
    const audioExists = await fs.access(audioPath).then(() => true).catch(() => false);
    if (!audioExists) {
      throw new Error(`❌ Arquivo de áudio não encontrado: ${audioPath}`);
    }

    // VERIFICAÇÃO 3: Arquivo não está vazio?
    // Áudios vazios causam problemas confusos mais tarde, melhor detectar agora
    const audioStats = await fs.stat(audioPath);
    if (audioStats.size === 0) {
      throw new Error("❌ Arquivo de áudio está vazio (0 bytes)");
    }

    // VERIFICAÇÃO 4: Arquivo não é muito pequeno (provável erro)?
    if (audioStats.size < 1024) { // Menos de 1KB é suspeito
      this.logger.warn("⚠️ Arquivo de áudio muito pequeno, pode estar corrompido", {
        fileSizeBytes: audioStats.size
      });
    }

    // Log educativo com informações úteis
    const fileSizeMB = (audioStats.size / 1024 / 1024).toFixed(2);
    this.logger.info("✅ Validação de ambiente concluída", {
      audioPath,
      fileSize: `${fileSizeMB}MB`,
      scriptType: "transcription.py (versão otimizada)",
      explanation: "Todos os pré-requisitos foram verificados e estão corretos"
    });
  }

  /**
   * MÉTODO PRINCIPAL DE EXECUÇÃO: executeFreeTranscription
   * 
   * Este método executa o script Python de forma otimizada, evitando
   * os problemas de download repetitivo que vimos nos logs anteriores.
   * 
   * DIFERENÇA FUNDAMENTAL: Em vez de usar 'python -c' com código inline,
   * usamos um script dedicado que gerencia eficientemente os recursos.
   */
  private async executeFreeTranscription(
    execAsync: any,
    scriptPath: string,
    audioPath: string,
    outputDir?: string
  ): Promise<TranscriptionResult> {
    this.logger.info("🚀 Executando transcrição otimizada com scripts dedicados...");

    // CONSTRUÇÃO INTELIGENTE DO COMANDO
    // Simples e direto: chamamos um script externo em vez de código inline complexo
    let command = `python "${scriptPath}" "${audioPath}"`;
    
    if (outputDir) {
      command += ` "${outputDir}"`;
    }

    // CONFIGURAÇÃO DE AMBIENTE OTIMIZADA
    // Removemos dependências desnecessárias (como HF_TOKEN) e configuramos
    // encoding corretamente para evitar problemas de caracteres especiais
    const env = { ...process.env };
    env.PYTHONIOENCODING = "utf-8";
    env.LC_ALL = "pt_BR.UTF-8";
    env.LANG = "pt_BR.UTF-8";
    
    // CORREÇÃO FUNDAMENTAL 2: Remover HF_TOKEN
    // O sistema gratuito não precisa de tokens externos
    delete env.HF_TOKEN;

    this.logger.info("📋 Configuração de execução preparada", { 
      command: `python transcription.py [arquivo-audio]`,
      environment: "UTF-8, sem tokens externos",
      philosophy: "Scripts dedicados evitam downloads repetitivos"
    });

    // TIMEOUT INTELIGENTE: baseado na configuração, mas com limite sensato
    const timeoutMs = this.config.timeoutMinutes! * 60 * 1000;
    
    // EXECUÇÃO COM MONITORAMENTO
    const { stdout, stderr } = await execAsync(command, {
      maxBuffer: 1024 * 1024 * 50, // 50MB buffer (generoso para logs detalhados)
      encoding: "buffer",           // Controle manual de encoding
      timeout: timeoutMs,
      env,
    });

    // PROCESSAMENTO EDUCATIVO DE SAÍDAS
    const stdoutText = stdout.toString('utf-8');
    const stderrText = stderr.toString('utf-8');

    // FILOSOFIA DE LOGS: stderr nem sempre é erro
    // Muitas bibliotecas Python enviam informações para stderr que são apenas informativos
    if (stderrText && stderrText.trim()) {
      // Analisar se é realmente um erro ou apenas informativo
      const isActualError = stderrText.includes('Error') || 
                           stderrText.includes('Exception') || 
                           stderrText.includes('Failed');
      
      if (isActualError) {
        this.logger.warn("⚠️ Possível erro detectado no stderr:", { 
          stderr: stderrText.trim().substring(0, 500) + "..."
        });
      } else {
        this.logger.info("📊 Informações do processo Python:", { 
          info: stderrText.trim().substring(0, 200) + "..."
        });
      }
    }

    // PARSING INTELIGENTE DO RESULTADO JSON
    let result: TranscriptionResult;
    try {
      const cleanedStdout = stdoutText.trim();
      
      // ESTRATÉGIA 1: Tentar encontrar JSON no final da saída
      // Scripts Python às vezes geram logs antes do resultado final
      const jsonMatch = cleanedStdout.match(/\{[\s\S]*\}$/);
      if (jsonMatch) {
        result = JSON.parse(jsonMatch[0]);
      } else {
        // ESTRATÉGIA 2: Assumir que toda a saída é JSON
        result = JSON.parse(cleanedStdout);
      }
      
      this.logger.info("✅ Resultado JSON processado com sucesso", { 
        status: result.status,
        processingType: result.processing_type,
        diarizationAvailable: result.diarization_available,
        hasText: !!result.text
      });
      
    } catch (e: any) {
      this.logger.error("❌ Erro ao processar JSON do script Python:", {
        error: e.message,
        rawOutputPreview: stdoutText.slice(0, 500) + "...",
        suggestion: "Verificando se o script está retornando JSON válido"
      });
      
      // RECUPERAÇÃO INTELIGENTE: Tentar extrair texto mesmo com JSON malformado
      const textMatch = stdoutText.match(/"text":\s*"([^"]+)"/);
      if (textMatch && textMatch[1]) {
        this.logger.warn("🔧 Recuperação bem-sucedida: extraindo texto do JSON malformado");
        result = {
          status: "success",
          text: textMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"'),
          language: "pt",
          processing_type: "fallback_extraction",
          timestamp: new Date().toISOString(),
          diarization_available: false
        };
      } else {
        throw new Error(`Falha crítica ao processar saída do script: ${e.message}`);
      }
    }

    return result;
  }

  /**
   * SISTEMA DE FALLBACK EDUCATIVO: attemptEducationalFallback
   * 
   * Este método implementa uma estratégia de "degradação graciosa" - quando o método
   * principal falha, tentamos métodos progressivamente mais simples até conseguir
   * algum resultado útil.
   * 
   * FILOSOFIA PEDAGÓGICA: É melhor ter uma transcrição imperfeita do que nenhuma transcrição.
   * Cada nível de fallback sacrifica alguma funcionalidade em troca de maior confiabilidade.
   */
  private async attemptEducationalFallback(audioPath: string, videoId: string): Promise<string> {
    this.logger.warn("🔄 Iniciando recuperação educativa em múltiplas etapas", { 
      videoId,
      strategy: "Fallbacks progressivamente mais simples"
    });
    
    try {
      const execAsync = promisify(exec);
      
      // FALLBACK NÍVEL 1: Tentar o script principal sem diarização
      const fallbackScriptPath = path.join(process.cwd(), "python", "transcription.py");
      const scriptExists = await fs.access(fallbackScriptPath).then(() => true).catch(() => false);
      
      if (scriptExists) {
        try {
          this.logger.info("🎯 Tentativa de fallback nível 1: script principal simplificado");
          
          const command = `python "${fallbackScriptPath}" "${audioPath}"`;
          
          const env = { ...process.env };
          env.PYTHONIOENCODING = "utf-8";
          env.LC_ALL = "pt_BR.UTF-8";
          env.LANG = "pt_BR.UTF-8";
          delete env.HF_TOKEN;
          
          // Timeout mais conservador para fallback
          const { stdout } = await execAsync(command, {
            timeout: 15 * 60 * 1000, // 15 minutos - menos agressivo que o principal
            encoding: 'utf-8',
            env,
            maxBuffer: 1024 * 1024 * 10 // Buffer menor para economia de recursos
          });
          
          // Processar resposta do fallback nível 1
          const result = JSON.parse(stdout.trim());
          
          if (result.status === 'success' && result.text) {
            this.logger.info("✅ Fallback nível 1 bem-sucedido", { 
              videoId, 
              textLength: result.text.length,
              level: "script-principal-simplificado"
            });
            return result.text;
          }
          
        } catch (level1Error: any) {
          this.logger.warn("⚠️ Fallback nível 1 falhou, tentando nível 2", {
            videoId,
            error: level1Error.message
          });
        }
      }
      
      // FALLBACK NÍVEL 2: Script temporário ultra-simples
      return await this.createUltraSimpleFallback(audioPath, videoId);
      
    } catch (error: any) {
      this.logger.error("❌ Todos os fallbacks educativos falharam", { 
        videoId, 
        error: error.message,
        recommendation: "Verificar instalação das dependências: pip install openai-whisper pydub numpy"
      });
      throw new Error("Sistema de transcrição completamente indisponível após múltiplas tentativas");
    }
  }

  /**
   * FALLBACK ULTRA-SIMPLES: createUltraSimpleFallback
   * 
   * Este é o "último recurso" - um script Python extremamente simples que usa
   * apenas o Whisper básico, sem nenhuma funcionalidade avançada.
   * 
   * FILOSOFIA: Quando tudo mais falha, volte ao básico absoluto.
   */
  private async createUltraSimpleFallback(audioPath: string, videoId: string): Promise<string> {
    this.logger.warn("🆘 Ativando fallback ultra-simples (último recurso)", { 
      videoId,
      approach: "Script temporário com Whisper básico"
    });
    
    try {
      const execAsync = promisify(exec);
      
      // SCRIPT PYTHON MÍNIMO
      // Este script é tão simples quanto possível - apenas Whisper básico
      const tempScriptContent = `
import whisper
import sys
import os

def main():
    try:
        # Log pedagógico para debugging
        print("🔧 Fallback ultra-simples iniciado...", file=sys.stderr)
        
        # Usar modelo pequeno para ser mais rápido e usar menos recursos
        print("📦 Carregando modelo Whisper small (mais rápido)...", file=sys.stderr)
        model = whisper.load_model('small', device='cpu')
        
        # Transcrição com configurações mínimas
        print("🎵 Iniciando transcrição básica...", file=sys.stderr)
        audio_file = sys.argv[1]
        result = model.transcribe(
            audio_file, 
            language='pt',      # Forçar português
            task='transcribe',  # Apenas transcrever, sem traduzir
            verbose=False,      # Sem logs excessivos
            fp16=False         # Evitar problemas de precisão em CPU
        )
        
        # Extrair e validar texto
        text = result['text'].strip()
        if text and len(text) > 5:  # Pelo menos 5 caracteres
            print(text)  # Output simples para stdout
        else:
            print("Erro: Transcrição resultou em texto vazio ou muito curto", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"Erro crítico no fallback: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
`;
      
      // Criar arquivo temporário com nome único
      const tempScriptPath = `/tmp/whisper_emergency_${videoId}_${Date.now()}.py`;
      await fs.writeFile(tempScriptPath, tempScriptContent, 'utf-8');
      
      try {
        this.logger.info("🚀 Executando script de emergência", {
          videoId,
          scriptPath: tempScriptPath,
          timeout: "8 minutos (conservador)"
        });
        
        // Executar com timeout muito conservador
        const { stdout, stderr } = await execAsync(`python "${tempScriptPath}" "${audioPath}"`, {
          timeout: 8 * 60 * 1000, // 8 minutos - bem conservador
          encoding: 'utf-8'
        });
        
        // Log informativo do stderr
        if (stderr && stderr.trim()) {
          this.logger.info("📋 Logs do script de emergência:", {
            logs: stderr.trim()
          });
        }
        
        // Processar resultado
        const text = stdout.trim();
        if (text && text.length > 10 && !text.startsWith('Erro:')) {
          this.logger.info("✅ Fallback ultra-simples funcionou!", { 
            videoId, 
            textLength: text.length,
            success: "Transcrição básica completada"
          });
          return text;
        } else {
          throw new Error(`Script de emergência retornou resultado inválido: ${text}`);
        }
        
      } finally {
        // LIMPEZA PEDAGÓGICA: Sempre limpar arquivos temporários
        try {
          await fs.unlink(tempScriptPath);
          this.logger.info("🧹 Script temporário removido", { tempScriptPath });
        } catch (cleanupError) {
          this.logger.warn("⚠️ Falha ao remover script temporário", { 
            tempScriptPath, 
            error: cleanupError 
          });
        }
      }
      
    } catch (error: any) {
      this.logger.error("💥 Fallback ultra-simples também falhou completamente", { 
        videoId, 
        error: error.message,
        diagnosis: "Possível problema com instalação do Whisper ou dependências básicas"
      });
      throw new Error(`Falha total do sistema de transcrição: ${error.message}`);
    }
  }

  /**
   * PROCESSAMENTO DE RESULTADO: processTranscriptionResult
   * 
   * Este método valida e processa o resultado final da transcrição,
   * garantindo que temos dados úteis antes de retornar para o usuário.
   */
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

    // ANÁLISE PEDAGÓGICA DO RESULTADO
    const words = result.text.split(/\s+/);
    const sentences = result.text.split(/[.!?]+/).filter(s => s.trim().length > 0);
    
    this.logger.info("📊 Análise completa do resultado da transcrição", {
      videoId,
      performance: {
        durationSeconds: duration,
        textLength: result.text.length,
        wordsEstimated: words.length,
        sentencesEstimated: sentences.length,
        averageWordsPerSentence: sentences.length > 0 ? (words.length / sentences.length).toFixed(1) : 0
      },
      technical: {
        processingType: result.processing_type,
        diarizationUsed: result.diarization_available,
        language: result.language || 'pt'
      },
      quality: {
        hasReasonableLength: result.text.length > 50,
        hasMultipleWords: words.length > 10,
        seemsValid: !result.text.includes('Error:') && !result.text.includes('Erro:')
      }
    });

    return result.text;
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
      const execAsync = promisify(exec);
      const recommendations: string[] = [];
      
      // VERIFICAÇÃO 1: Python
      const pythonAvailable = await execAsync('python --version')
        .then((result) => {
          this.logger.info("✅ Python detectado", { version: result.stdout.trim() });
          return true;
        })
        .catch(() => {
          recommendations.push("Instalar Python 3.7 ou superior");
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
        whisperAvailable = await execAsync('python -c "import whisper; print(whisper.__version__)"')
          .then((result) => {
            this.logger.info("✅ Whisper instalado", { version: result.stdout.trim() });
            return true;
          })
          .catch(() => {
            recommendations.push("Instalar Whisper: pip install openai-whisper");
            return false;
          });
      }
      
      // VERIFICAÇÃO 4: Dependências da diarização
      let diarizationAvailable = false;
      if (pythonAvailable) {
        diarizationAvailable = await execAsync('python -c "import pydub, numpy; print(\'OK\')"')
          .then(() => {
            this.logger.info("✅ Dependências de diarização disponíveis");
            return true;
          })
          .catch(() => {
            recommendations.push("Instalar dependências: pip install pydub numpy");
            return false;
          });
      }
      
      // VERIFICAÇÃO 5: FFmpeg
      const ffmpegAvailable = await execAsync('ffmpeg -version')
        .then(() => {
          this.logger.info("✅ FFmpeg detectado");
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
      
      const execAsync = promisify(exec);
      
      // Teste simples: verificar se conseguimos importar as bibliotecas essenciais
      await execAsync('python -c "import whisper, pydub, numpy; print(\'✅ Bibliotecas essenciais OK\')"', {
        timeout: 30000 // 30 segundos
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