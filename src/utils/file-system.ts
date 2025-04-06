import fs from "fs/promises";
import path from "path";
import { Logger } from "./logger";

export class FileSystem {
  constructor(private logger: Logger) {}

  public async ensureTempDir(): Promise<void> {
    const tempDir = path.join(process.cwd(), "temp");
    
    try {
      await fs.mkdir(tempDir, { recursive: true, mode: 0o777 });
      await fs.chmod(tempDir, 0o777);
      this.logger.info("Diretório temporário criado/verificado com sucesso", {
        path: tempDir,
      });
    } catch (error: any) {
      this.logger.error("Erro ao criar/verificar diretório temporário:", {
        error: error.message,
        path: tempDir,
      });
      throw error;
    }
  }

  public async removeFile(filePath: string): Promise<boolean> {
    try {
      await fs.unlink(filePath);
      return true;
    } catch (error: any) {
      if (error.code !== 'ENOENT') {
        this.logger.error(`Erro ao remover arquivo: ${filePath}`, { error: error.message });
      }
      return false;
    }
  }

  public async removeDirectory(dirPath: string, recursive = true): Promise<boolean> {
    try {
      await fs.rm(dirPath, { recursive, force: true });
      return true;
    } catch (error: any) {
      if (error.code !== 'ENOENT') {
        this.logger.error(`Erro ao remover diretório: ${dirPath}`, { error: error.message });
      }
      return false;
    }
  }
}