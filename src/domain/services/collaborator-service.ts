import { Logger } from "../../utils/logger";
import { CollaboratorRepository } from "../../data/repositories/collaborator-repository";
import { Credential } from "../../domain/models/Credentials";

export interface TokenData {
  access_token: string;
  refresh_token?: string;
  expiry_date?: number;
  scope?: string;
  token_type?: string;
}

export interface CollaboratorData {
  name: string;
  picture?: string;
  user_id: string;
  email: string;
  access_token: string;
  refresh_token?: string;
  expiry_date?: number;
  scope?: string;
  token_type?: string;
}


export class CollaboratorService {
  constructor(
    private collaboratorRepository: CollaboratorRepository,
    private logger: Logger
  ) {}

  /**
   * Obtém todos os colaboradores ativos
   */
  public async getAllActiveCollaborators(): Promise<Credential[]> {
    try {
      return await this.collaboratorRepository.getAllActiveCollaborators();
    } catch (error: any) {
      this.logger.error("Erro ao obter colaboradores ativos:", error);
      throw error;
    }
  }

  /**
   * Obtém os tokens de um usuário específico
   */
  public async getUserTokens(email: string): Promise<Credential | null> {
    try {
      const tokens = await this.collaboratorRepository.getUserTokens(email);
      if (!tokens) {
        this.logger.warn(`Tokens não encontrados para o usuário: ${email}`);
      }
      return tokens;
    } catch (error: any) {
      this.logger.error(`Erro ao obter tokens do usuário ${email}:`, error);
      throw error;
    }
  }

  /**
   * Atualiza os tokens de um usuário
   */
  public async updateUserTokens(email: string, tokens: TokenData): Promise<Credential | null> {
    try {
      this.logger.info(`Atualizando tokens para ${email}`);
      return await this.collaboratorRepository.updateUserTokens(email, tokens);
    } catch (error: any) {
      this.logger.error(`Erro ao atualizar tokens do usuário ${email}:`, error);
      throw error;
    }
  }

  /**
   * Salva as credenciais de um novo colaborador ou atualiza as existentes
   */
  public async saveCredentials(credentialData: {
    user_id: string;
    name: string;
    email: string;
    picture?: string;
    access_token: string;
    refresh_token?: string;
    scope?: string;
    token_type?: string;
    expiry_date?: number;
  }): Promise<void> {
    try {
      this.logger.info(`Salvando credenciais para ${credentialData.email}`);
      
      // Usar o novo método que verifica e atualiza se necessário
      await this.collaboratorRepository.saveOrUpdateCredentials(credentialData);
      
      this.logger.info(`Credenciais salvas com sucesso para ${credentialData.email}`);
    } catch (error: any) {
      this.logger.error(`Erro ao salvar credenciais para ${credentialData.email}:`, error);
      throw new Error(`Erro ao salvar credenciais: ${error.message}`);
    }
  }

  /**
   * Verifica se um usuário existe pelo email
   */
  public async userExists(email: string): Promise<boolean> {
    try {
      const tokens = await this.collaboratorRepository.getUserTokens(email);
      return tokens !== null;
    } catch (error: any) {
      this.logger.error(`Erro ao verificar existência do usuário ${email}:`, error);
      return false;
    }
  }

  /**
   * Verifica se o usuário tem credencial ativa (Drive conectado)
   */
  public async hasActiveDrive(userId: string): Promise<boolean> {
    return this.collaboratorRepository.hasActiveDrive(userId);
  }

  /**
   * Obtém informações básicas do colaborador
   */
  public async getCollaboratorInfo(email: string): Promise<{
    userId: string;
    name: string;
    email: string;
    picture?: string;
    driveConnected: boolean;
  } | null> {
    try {
      const credentials = await this.collaboratorRepository.getUserTokens(email);
      if (!credentials) return null;
      const driveConnected = await this.hasActiveDrive(credentials.userId);
      return {
        userId: credentials.userId,
        name: credentials.name,
        email: credentials.email,
        picture: credentials.picture,
        driveConnected
      };
    } catch (error: any) {
      this.logger.error(`Erro ao obter informações do colaborador ${email}:`, error);
      return null;
    }
  }

  /**
   * Busca colaborador por e-mail e retorna com status de driveConnected
   */
  public async getCollaboratorByEmail(email: string) {
    const collaborator = await this.collaboratorRepository.getCollaboratorByEmail(email);
    if (!collaborator) return null;
    const driveConnected = await this.hasActiveDrive(collaborator.userId);
    return { ...collaborator, driveConnected };
  }

  /**
   * Cria um novo colaborador manualmente (admin)
   */
  public async createCollaborator(data: { name: string; email: string; password: string; isAdmin?: boolean }): Promise<void> {
    try {
      await this.collaboratorRepository.createCollaborator(data);
      this.logger.info(`Colaborador criado manualmente: ${data.email}`);
    } catch (error: any) {
      this.logger.error('Erro ao criar colaborador manualmente:', error);
      throw error;
    }
  }
}
