import { Request, Response } from "express";
import { Logger } from "../../utils/logger";
import { ConfigRepository } from "../../data/repositories/config-repository";
// Importação compatível com TypeScript e CommonJS para node-fetch
let fetch: typeof import('node-fetch').default;
try {
  fetch = require('node-fetch');
  if (fetch.default) fetch = fetch.default;
} catch (e) {
  // fallback para import, se necessário
}

export class ConfigController {
  constructor(
    private configRepository: ConfigRepository,
    private logger: Logger
  ) {}

  public async getRootFolder(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.userId) {
        res.status(401).json({ error: "Usuário não autenticado" });
        return;
      }
      const folders = await this.configRepository.getRootFolders(user.userId);
      res.status(200).json({ folders });
    } catch (error: any) {
      this.logger.error("Erro ao buscar pastas raiz:", error);
      res.status(500).json({ error: error.message });
    }
  }

  public async setRootFolder(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.userId) {
        res.status(401).json({ error: "Usuário não autenticado" });
        return;
      }
      const { folder } = req.body;
      if (!folder || !Array.isArray(folder) || folder.length === 0) {
        res.status(400).json({ error: "Lista de pastas é obrigatória" });
        return;
      }
      // Validar cada pasta: aceitar link completo, id ou nome
      for (const f of folder) {
        if (!this.isValidDriveFolder(f)) {
          let msg = `Pasta inválida: ${f}. Aceite links completos do Google Drive, IDs ou nomes.`;
          res.status(400).json({ error: msg });
          return;
        }
      }
      await this.configRepository.setRootFolders(folder, user.userId);
      res.status(200).json({ message: "Pastas configuradas com sucesso" });
    } catch (error: any) {
      this.logger.error("Erro ao configurar pastas raiz:", error);
      res.status(500).json({ error: error.message });
    }
  }

  public async getTranscriptionConfig(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.userId) {
        res.status(401).json({ error: "Usuário não autenticado" });
        return;
      }
      const config = await this.configRepository.getTranscriptionConfig(user.userId);
      res.status(200).json(config);
    } catch (error: any) {
      this.logger.error("Erro ao buscar configuração de transcrição:", error);
      res.status(500).json({ error: error.message });
    }
  }

  public async setTranscriptionConfig(req: Request, res: Response): Promise<void> {
    try {
      const user = (req as any).user;
      if (!user || !user.userId) {
        res.status(401).json({ error: "Usuário não autenticado" });
        return;
      }
      const { transcriptionFolder, moveVideoAfterTranscription, videoDestinationFolder } = req.body;
      const config = {
        transcriptionFolder: transcriptionFolder || null,
        moveVideoAfterTranscription: Boolean(moveVideoAfterTranscription),
        videoDestinationFolder: moveVideoAfterTranscription ? videoDestinationFolder : null
      };
      await this.configRepository.setTranscriptionConfig(config, user.userId);
      res.status(200).json({ message: "Configuração de transcrição salva com sucesso" });
    } catch (error: any) {
      this.logger.error("Erro ao configurar transcrição:", error);
      res.status(500).json({ error: error.message });
    }
  }

  public async getWebhooks(req: Request, res: Response): Promise<void> {
    try {
      // Apenas admin pode ver webhooks
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: "Acesso restrito a administradores." });
        return;
      }
      const webhooks = await this.configRepository.getWebhooks();
      res.status(200).json({ webhooks });
    } catch (error: any) {
      this.logger.error("Erro ao buscar webhooks:", error);
      res.status(500).json({ error: error.message });
    }
  }

  public async setWebhooks(req: Request, res: Response): Promise<void> {
    try {
      // Apenas admin pode editar webhooks
      const user = (req as any).user;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: "Acesso restrito a administradores." });
        return;
      }
      const { webhooks } = req.body;
      if (!Array.isArray(webhooks)) {
        res.status(400).json({ error: "Lista de webhooks é obrigatória" });
        return;
      }
      // Eventos permitidos
      const ALLOWED_EVENTS = [
        'transcription_completed',
        'transcription_failed',
        'video_processing',
      ];
      // Validar webhooks
      for (const webhook of webhooks) {
        if (!webhook.url || !webhook.name) {
          res.status(400).json({ error: "URL e nome são obrigatórios para cada webhook" });
          return;
        }
        if (!Array.isArray(webhook.events) || webhook.events.length === 0) {
          res.status(400).json({ error: `Webhook '${webhook.name}' deve ter pelo menos um evento selecionado.` });
          return;
        }
        for (const ev of webhook.events) {
          if (!ALLOWED_EVENTS.includes(ev)) {
            res.status(400).json({ error: `Evento inválido '${ev}' no webhook '${webhook.name}'. Eventos permitidos: ${ALLOWED_EVENTS.join(', ')}` });
            return;
          }
        }
      }
      await this.configRepository.setWebhooks(webhooks);
      res.status(200).json({ message: "Webhooks configurados com sucesso" });
    } catch (error: any) {
      this.logger.error("Erro ao configurar webhooks:", error);
      res.status(500).json({ error: error.message });
    }
  }

  public async testWebhook(req: Request, res: Response): Promise<void> {
    try {
      const { url, name, description, events, active } = req.body;
      if (!url) {
        res.status(400).json({ error: "URL do webhook é obrigatória" });
        return;
      }
      // Payload de teste
      const testPayload = {
        event: "test",
        timestamp: new Date().toISOString(),
        message: "Este é um teste de webhook",
        data: {
          videoId: "test-video-id",
          videoName: "Vídeo de Teste",
          status: "test"
        }
      };
      // Enviar POST real para o webhook
      let responseStatus = null;
      let responseText = null;
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(testPayload)
        });
        responseStatus = response.status;
        responseText = await response.text();
      } catch (err: any) {
        this.logger.error("Erro ao enviar POST de teste para webhook:", err);
        res.status(500).json({ error: `Falha ao enviar POST para o webhook: ${err.message}` });
        return;
      }
      this.logger.info("Teste de webhook enviado", { url, payload: testPayload, responseStatus, responseText });
      res.status(200).json({ 
        message: `Webhook testado com sucesso (status ${responseStatus})`,
        payload: testPayload,
        responseStatus,
        responseText
      });
    } catch (error: any) {
      this.logger.error("Erro ao testar webhook:", error);
      res.status(500).json({ error: error.message });
    }
  }

  private isValidDriveFolder(input: string): boolean {
    const linkRegex = /^https:\/\/drive\.google\.com\/drive\/folders\/[a-zA-Z0-9_-]{10,}/;
    const idRegex = /^[a-zA-Z0-9_-]{10,}$/;
    const nameRegex = /\S+/;
    return linkRegex.test(input) || idRegex.test(input) || nameRegex.test(input);
  }
} 