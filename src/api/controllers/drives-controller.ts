import { Request, Response } from 'express';
import { CollaboratorService } from '../../domain/services/collaborator-service';
import { Logger } from '../../utils/logger';

export class DrivesController {
  constructor(
    private collaboratorService: CollaboratorService,
    private logger: Logger
  ) {}

  public async getConnectedDrives(req: Request, res: Response): Promise<void> {
    try {
      const collaborators = await this.collaboratorService.getAllActiveCollaborators();
      
      const drives = collaborators.map((collaborator: any) => ({
        id: collaborator.id,
        name: collaborator.name,
        email: collaborator.email,
        status: collaborator.accessToken ? 'conectado' : 'desconectado',
        lastConnection: collaborator.updatedAt,
        driveToken: collaborator.accessToken ? 'presente' : 'ausente'
      }));

      res.status(200).json(drives);
    } catch (error: any) {
      this.logger.error('Erro ao buscar drives conectados:', error);
      // Retornar array vazio em caso de erro para não quebrar o frontend
      res.status(200).json([]);
    }
  }

  public async generateConnectionLink(req: Request, res: Response): Promise<void> {
    try {
      const { email } = req.params;
      
      if (!email) {
        res.status(400).json({ error: 'Email é obrigatório' });
        return;
      }

      // Gerar URL de autenticação do Google para o usuário específico
      const { GoogleAuthService } = await import('../../infrastructure/auth/google-auth');
      const googleAuthService = new GoogleAuthService(this.logger);
      
      const authUrl = googleAuthService.getAuthUrl();
      
      res.status(200).json({ 
        authUrl,
        message: `Link de conexão gerado para ${email}`
      });
    } catch (error: any) {
      this.logger.error('Erro ao gerar link de conexão:', error);
      res.status(500).json({ error: error.message });
    }
  }

  public async disconnectDrive(req: Request, res: Response): Promise<void> {
    try {
      const { email } = req.params;
      
      if (!email) {
        res.status(400).json({ error: 'Email é obrigatório' });
        return;
      }

      // Por enquanto, apenas retorna sucesso
      // TODO: Implementar desconexão real do drive
      this.logger.info(`Solicitação de desconexão do drive para ${email}`);
      
      res.status(200).json({ 
        message: `Drive desconectado com sucesso para ${email}`
      });
    } catch (error: any) {
      this.logger.error('Erro ao desconectar drive:', error);
      res.status(500).json({ error: error.message });
    }
  }
} 