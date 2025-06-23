import { Logger } from "../../utils/logger";
import fs from "fs/promises";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

export class TranscriptionProcessor {
  constructor(private logger: Logger) {}

  public async transcribeAudio(audioPath: string, videoId: string): Promise<string> {
    this.logger.info(`TranscriptionProcessor initialized for videoId: ${videoId}`);
    const execAsync = promisify(exec);

    // Caminho absoluto para o script Python
    const scriptPath = path.join(process.cwd(), "python", "transcribe.py");

    try {
      this.logger.info("Iniciando transcrição do áudio...", { audioPath });

      // Verificar se o script Python existe
      const scriptExists = await fs.access(scriptPath).then(() => true).catch(() => false);
      if (!scriptExists) {
        this.logger.error(`Script Python não encontrado: ${scriptPath}`);
        return "Erro: Script de transcrição não encontrado. Transcrição não disponível.";
      }

      // Verificar se o arquivo de áudio existe
      const audioExists = await fs.access(audioPath).then(() => true).catch(() => false);
      if (!audioExists) {
        this.logger.error(`Arquivo de áudio não encontrado: ${audioPath}`);
        return "Erro: Arquivo de áudio não encontrado. Transcrição não disponível.";
      }

      // enviando para o python transcrever
      try {
        const startTime = Date.now();
        const { stdout } = await execAsync(`py "${scriptPath}" "${audioPath}"`, {
          maxBuffer: 1024 * 1024 * 10,
          encoding: "utf8",
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
          audioPath,
          chunks: result.chunks,
        });

        return result.text;
      } catch (pythonError: any) {
        // Log the error but continue with alternative approach
        this.logger.error("Erro executando script Python:", {
          error: pythonError.message,
          audioPath,
        });
      
        // Return fallback message if Python script fails
        return "Este vídeo não pôde ser transcrito devido a um erro técnico. " +
               "Por favor, tente novamente mais tarde ou entre em contato com o suporte.";
      }
    } catch (error: any) {
      this.logger.error("Erro fatal na transcrição:", {
        error: error.message,
        audioPath,
      });
      throw new Error(`Erro na transcrição: ${error.message}`);
    }
  }
}