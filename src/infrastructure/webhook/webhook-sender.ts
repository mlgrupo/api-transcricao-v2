import { Logger } from "../../utils/logger";

interface WebhookData {
  status: string;
  [key: string]: any;
}

export class WebhookService {
  private lastNotifications: Map<string, {
    status: string;
    lastSent: Date;
    count: number;
  }>;
  
  private notificationDebounceMs: number;

  constructor(private logger: Logger) {
    this.lastNotifications = new Map();
    this.notificationDebounceMs = 30000; // 30 segundos
  }

  public async sendNotification(webhookUrl: string, data: WebhookData): Promise<boolean> {
    try {
      const { videoId, status } = data;
      
      // Se não tiver videoId ou status, enviar normalmente
      if (!videoId || !status) {
        this.logger.info(`Enviando notificação webhook para ${webhookUrl}`, data);
        return await this.sendWebhookRequest(webhookUrl, data);
      }
      
      const now = new Date();
      const notificationKey = `${videoId}-${status}`;
      const lastNotification = this.lastNotifications.get(notificationKey);
      
      // Verificar se já enviamos este mesmo status para este vídeo recentemente
      if (lastNotification) {
        const timeSinceLastMs = now.getTime() - lastNotification.lastSent.getTime();
        
        if (timeSinceLastMs < this.notificationDebounceMs) {
          lastNotification.count += 1;
          this.logger.info(`Ignorando notificação webhook duplicada (${lastNotification.count}x): ${videoId} - ${status}`);
          return true;
        }
        
        // Se a notificação for do mesmo tipo, mas já passou tempo suficiente, atualizamos o contador
        this.logger.info(`Reenviando notificação após ${Math.floor(timeSinceLastMs / 1000)}s: ${videoId} - ${status}`);
      }
      
      // Enviar a notificação
      const result = await this.sendWebhookRequest(webhookUrl, data);
      
      // Atualizar o registro desta notificação
      this.lastNotifications.set(notificationKey, {
        status,
        lastSent: now,
        count: lastNotification ? lastNotification.count + 1 : 1
      });
      
      // Limpar notificações antigas
      this.clearOldNotifications();
      
      return result;
    } catch (error: any) {
      this.logger.error('Erro ao enviar notificação webhook:', error);
      return false;
    }
  }

  private async sendWebhookRequest(webhookUrl: string, data: any): Promise<boolean> {
    try {
      this.logger.info(`Enviando notificação webhook para ${webhookUrl}`, data);
      
      const response = await fetch(webhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });

      if (!response.ok) {
        throw new Error(`Falha na requisição webhook com status ${response.status}`);
      }

      this.logger.info('Notificação webhook enviada com sucesso');
      return true;
    } catch (error: any) {
      this.logger.error('Erro ao enviar notificação webhook:', error);
      return false;
    }
  }

  private clearOldNotifications(): void {
    const now = new Date();
    const maxAgeMs = 5 * 60 * 1000; // 5 minutos
    
    for (const [key, notification] of this.lastNotifications.entries()) {
      if (now.getTime() - notification.lastSent.getTime() > maxAgeMs) {
        this.lastNotifications.delete(key);
      }
    }
  }
}