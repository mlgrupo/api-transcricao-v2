import winston from "winston";
import { LogRepository } from "../data/repositories/log-repository";

export class Logger {
  private logger: winston.Logger;
  private logRepository: LogRepository;

  constructor() {
    this.logRepository = new LogRepository();
    const customFormat = winston.format.printf(({ level, message, timestamp, ...metadata }) => {
      let msg = `${timestamp} [${level.toUpperCase()}]: ${message}`;
      if (Object.keys(metadata).length > 0) {
        msg += ` | ${JSON.stringify(metadata)}`;
      }
      return msg;
    });

    this.logger = winston.createLogger({
      level: process.env.LOG_LEVEL || "debug",
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.colorize(),
        customFormat
      ),
      transports: [
        new winston.transports.File({
          filename: "error.log",
          level: "error",
          format: winston.format.combine(
            winston.format.timestamp(),
            winston.format.json()
          ),
        }),
        new winston.transports.File({
          filename: "combined.log",
          format: winston.format.combine(
            winston.format.timestamp(),
            winston.format.json()
          ),
        }),
        new winston.transports.Console({
          format: winston.format.combine(
            winston.format.colorize(),
            customFormat
          ),
        }),
      ],
    });
  }

  private async saveToRepository(level: string, message: string, meta?: any): Promise<void> {
    if (!this.logRepository) return;

    // Salvar apenas logs de erro ou logs de conclusão de transcrição
    if (level === "error" || (level === "info" && message.includes("Transcrição concluída"))) {
      try {
        await this.logRepository.saveLog(level, message, meta);
      } catch (error: any) {
        this.logger.warn("Falha ao salvar log no repositório:", { error: error.message });
      }
    }
  }

  public async info(message: string, meta?: any): Promise<void> {
    await this.saveToRepository("info", message, meta);
    this.logger.info(message, meta);
  }

  public async warn(message: string, meta?: any): Promise<void> {
    this.logger.warn(message, meta);
  }

  public async error(message: string, meta?: any): Promise<void> {
    await this.saveToRepository("error", message, meta);
    this.logger.error(message, meta);
  }

  public async debug(message: string, meta?: any): Promise<void> {
    this.logger.debug(message, meta);
  }
}