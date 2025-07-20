import { Request, Response } from "express";
import { Logger } from "../../utils/logger";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

export class RobustTranscriptionController {
  constructor(private logger: Logger) {}

  /**
   * Obtém o status da arquitetura robusta
   */
  public async getStatus(req: Request, res: Response): Promise<void> {
    try {
      const scriptPath = path.join(process.cwd(), "python", "robust_transcription_adapter.py");
      
      // Executar comando para obter status
      const execAsync = promisify(exec);
      const command = `python "${scriptPath}" --status`;
      
      const { stdout } = await execAsync(command);
      
      try {
        const status = JSON.parse(stdout);
        res.status(200).json({
          success: true,
          status
        });
      } catch (parseError) {
        // Se não conseguir fazer parse, retornar como texto
        res.status(200).json({
          success: true,
          status: stdout,
          raw: true
        });
      }
      
    } catch (error: any) {
      this.logger.error("Erro ao obter status da arquitetura robusta:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }

  /**
   * Testa a arquitetura robusta
   */
  public async testArchitecture(req: Request, res: Response): Promise<void> {
    try {
      const scriptPath = path.join(process.cwd(), "python", "test_robust_integration.py");
      
      // Verificar se o script de teste existe
      const fs = require("fs").promises;
      try {
        await fs.access(scriptPath);
      } catch {
        res.status(404).json({
          success: false,
          error: "Script de teste não encontrado. Execute setup_robust_integration.py primeiro."
        });
        return;
      }
      
      // Executar teste
      const execAsync = promisify(exec);
      const command = `python "${scriptPath}"`;
      
      const { stdout, stderr } = await execAsync(command);
      
      res.status(200).json({
        success: true,
        stdout,
        stderr,
        message: "Teste executado com sucesso"
      });
      
    } catch (error: any) {
      this.logger.error("Erro ao testar arquitetura robusta:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }

  /**
   * Configura a arquitetura robusta
   */
  public async setupArchitecture(req: Request, res: Response): Promise<void> {
    try {
      const scriptPath = path.join(process.cwd(), "python", "setup_robust_integration.py");
      
      // Verificar se o script existe
      const fs = require("fs").promises;
      try {
        await fs.access(scriptPath);
      } catch {
        res.status(404).json({
          success: false,
          error: "Script de configuração não encontrado"
        });
        return;
      }
      
      // Executar configuração
      const execAsync = promisify(exec);
      const command = `python "${scriptPath}"`;
      
      const { stdout, stderr } = await execAsync(command);
      
      res.status(200).json({
        success: true,
        stdout,
        stderr,
        message: "Configuração executada com sucesso"
      });
      
    } catch (error: any) {
      this.logger.error("Erro ao configurar arquitetura robusta:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }

  /**
   * Obtém métricas de recursos
   */
  public async getResourceMetrics(req: Request, res: Response): Promise<void> {
    try {
      const scriptPath = path.join(process.cwd(), "python", "robust_transcription_adapter.py");
      
      // Executar comando para obter métricas
      const execAsync = promisify(exec);
      const command = `python "${scriptPath}" --metrics`;
      
      const { stdout } = await execAsync(command);
      
      try {
        const metrics = JSON.parse(stdout);
        res.status(200).json({
          success: true,
          metrics
        });
      } catch (parseError) {
        res.status(200).json({
          success: true,
          metrics: stdout,
          raw: true
        });
      }
      
    } catch (error: any) {
      this.logger.error("Erro ao obter métricas de recursos:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }

  /**
   * Atualiza configuração da arquitetura robusta
   */
  public async updateConfig(req: Request, res: Response): Promise<void> {
    try {
      const { config } = req.body;
      
      if (!config) {
        res.status(400).json({
          success: false,
          error: "Configuração é obrigatória"
        });
        return;
      }
      
      const configPath = path.join(process.cwd(), "python", "robust_integration_config.json");
      const fs = require("fs").promises;
      
      // Salvar nova configuração
      await fs.writeFile(configPath, JSON.stringify(config, null, 2), "utf8");
      
      this.logger.info("Configuração da arquitetura robusta atualizada", { config });
      
      res.status(200).json({
        success: true,
        message: "Configuração atualizada com sucesso"
      });
      
    } catch (error: any) {
      this.logger.error("Erro ao atualizar configuração:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }

  /**
   * Obtém configuração atual
   */
  public async getConfig(req: Request, res: Response): Promise<void> {
    try {
      const configPath = path.join(process.cwd(), "python", "robust_integration_config.json");
      const fs = require("fs").promises;
      
      try {
        const configData = await fs.readFile(configPath, "utf8");
        const config = JSON.parse(configData);
        
        res.status(200).json({
          success: true,
          config
        });
      } catch (fileError) {
        res.status(404).json({
          success: false,
          error: "Arquivo de configuração não encontrado"
        });
      }
      
    } catch (error: any) {
      this.logger.error("Erro ao obter configuração:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }

  /**
   * Força uso da arquitetura robusta para próximo processamento
   */
  public async forceRobustMode(req: Request, res: Response): Promise<void> {
    try {
      const { enabled } = req.body;
      
      if (typeof enabled !== "boolean") {
        res.status(400).json({
          success: false,
          error: "Parâmetro 'enabled' deve ser boolean"
        });
        return;
      }
      
      // Criar arquivo de flag para forçar modo
      const flagPath = path.join(process.cwd(), "python", ".force_robust_mode");
      const fs = require("fs").promises;
      
      if (enabled) {
        await fs.writeFile(flagPath, "1", "utf8");
        this.logger.info("Modo robusto forçado ativado");
      } else {
        try {
          await fs.unlink(flagPath);
          this.logger.info("Modo robusto forçado desativado");
        } catch {
          // Arquivo não existe, não fazer nada
        }
      }
      
      res.status(200).json({
        success: true,
        message: `Modo robusto ${enabled ? "ativado" : "desativado"} com sucesso`
      });
      
    } catch (error: any) {
      this.logger.error("Erro ao configurar modo robusto:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }

  /**
   * Obtém logs da arquitetura robusta
   */
  public async getLogs(req: Request, res: Response): Promise<void> {
    try {
      const { lines = 100 } = req.query;
      const logPath = path.join(process.cwd(), "python", "robust_architecture.log");
      
      const fs = require("fs").promises;
      
      try {
        const logContent = await fs.readFile(logPath, "utf8");
        const logLines = logContent.split("\n").filter((line: string) => line.trim());
        
        // Retornar últimas N linhas
        const lastLines = logLines.slice(-parseInt(lines as string));
        
        res.status(200).json({
          success: true,
          logs: lastLines,
          totalLines: logLines.length
        });
      } catch (fileError) {
        res.status(404).json({
          success: false,
          error: "Arquivo de log não encontrado"
        });
      }
      
    } catch (error: any) {
      this.logger.error("Erro ao obter logs:", error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }
} 