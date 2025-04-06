import { Repository } from "typeorm";
import { AppDataSource } from "../data-source";
import { ApplicationLog } from "../../domain/models/ApplicationLog";

export class LogRepository {
  private repository: Repository<ApplicationLog>;

  constructor() {
    this.repository = AppDataSource.getRepository(ApplicationLog);
  }

  public async saveLog(level: string, message: string, metadata?: Record<string, any>): Promise<void> {
    console.log('Salvando log:', { level, message, metadata });
    const log = this.repository.create({ level, message, metadata });
    await this.repository.save(log);
  }
}
