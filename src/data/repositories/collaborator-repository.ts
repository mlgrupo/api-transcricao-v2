import { Repository } from "typeorm";
import { AppDataSource } from "../data-source";
import { Collaborator } from "../../domain/models/Collaborators";
import { Credential } from "../../domain/models/Credentials";
import { Logger } from "../../utils/logger";
import { v4 as uuidv4 } from 'uuid';

export class CollaboratorRepository {
  private repository: Repository<Collaborator>;
  private credentialRepository: Repository<Credential>;
  private logger: Logger;
  private FOLDER_ROOT_NAME: string = process.env.ROOT_FOLDER_NAME || 'Meet Recordings';

  constructor(logger: Logger) {
    this.repository = AppDataSource.getRepository(Collaborator);
    this.credentialRepository = AppDataSource.getRepository(Credential);
    this.logger = logger;
  }

  public async getCollaboratorById(userId: string): Promise<Collaborator | null> {
    try {
      return await this.repository.findOne({
        where: { userId }
      });
    } catch (error: any) {
      this.logger.error("Erro ao buscar colaborador por ID:", error);
      throw error;
    }
  }

  public async getAllActiveCollaborators(): Promise<Credential[]> {
    try {
      return await this.credentialRepository
        .createQueryBuilder("cred")
        .distinctOn(["cred.user_id"])
        .where("cred.ativo = :ativo", { ativo: true })
        .orderBy("cred.user_id")
        .addOrderBy("cred.updated_at", "DESC")
        .getMany();
    } catch (error: any) {
      this.logger.error("Erro ao buscar colaboradores ativos:", error);
      throw error;
    }
  }

  public async saveOrUpdateCredentials(credentialData: {
    user_id: string;
    name: string;
    email: string;
    picture?: string;
    access_token: string;
    refresh_token?: string;
    scope?: string;
    token_type?: string;
    expiry_date?: number;
  }): Promise<Credential> {
    try {
      // Verificar se o usuário já existe na tabela credentials
      const existingCredential = await this.credentialRepository.findOne({
        where: { email: credentialData.email }
      });

      // Buscar colaborador pelo email primeiro
      let collaborator = await this.repository.findOne({
        where: { email: credentialData.email }
      });

      // Se encontrou colaborador pelo email, atualiza os campos (inclusive userId)
      if (collaborator) {
        collaborator.userId = credentialData.user_id;
        collaborator.name = credentialData.name;
        collaborator.picture = credentialData.picture;
        collaborator.folderRootName = this.FOLDER_ROOT_NAME;
        await this.repository.save(collaborator);
        this.logger.info(`Atualizado colaborador existente para ${credentialData.email}`);
      } else {
        // Se não encontrou colaborador, cria um novo
        this.logger.info(`Criando novo colaborador para ${credentialData.email}`);
        collaborator = new Collaborator();
        collaborator.userId = credentialData.user_id;
        collaborator.name = credentialData.name;
        collaborator.email = credentialData.email;
        collaborator.picture = credentialData.picture;
        collaborator.folderRootName = this.FOLDER_ROOT_NAME;
        await this.repository.save(collaborator);
        this.logger.info(`Colaborador criado com sucesso para ${credentialData.email}`);
      }

      if (existingCredential) {
        this.logger.info(`Atualizando credenciais para ${credentialData.email}`);
        existingCredential.name = credentialData.name;
        existingCredential.picture = credentialData.picture;
        existingCredential.accessToken = credentialData.access_token;
        if (credentialData.refresh_token) {
          existingCredential.refreshToken = credentialData.refresh_token;
        }
        existingCredential.scope = credentialData.scope;
        existingCredential.tokenType = credentialData.token_type;
        existingCredential.expiryDate = credentialData.expiry_date;
        existingCredential.updatedAt = new Date();
        return await this.credentialRepository.save(existingCredential);
      } else {
        this.logger.info(`Criando novas credenciais para ${credentialData.email}`);
        const credential = new Credential();
        credential.userId = credentialData.user_id;
        credential.name = credentialData.name;
        credential.email = credentialData.email;
        credential.picture = credentialData.picture;
        credential.accessToken = credentialData.access_token;
        credential.refreshToken = credentialData.refresh_token;
        credential.scope = credentialData.scope;
        credential.tokenType = credentialData.token_type;
        credential.expiryDate = credentialData.expiry_date;
        return await this.credentialRepository.save(credential);
      }
    } catch (error: any) {
      this.logger.error(`Erro ao salvar ou atualizar credenciais para ${credentialData.email}:`, error);
      throw new Error(`Erro ao salvar ou atualizar credenciais: ${error.message}`);
    }
  }

  public async saveCredentials(data: {
    name: string;
    picture?: string;
    user_id: string;
    email: string;
    access_token: string;
    refresh_token?: string;
    expiry_date?: number;
    scope?: string;
    token_type?: string;
  }): Promise<Credential> {
    try {
      const credential = new Credential();
      credential.userId = data.user_id;
      credential.name = data.name;
      credential.email = data.email;
      credential.picture = data.picture;
      credential.accessToken = data.access_token;
      credential.refreshToken = data.refresh_token;
      credential.expiryDate = data.expiry_date;
      credential.scope = data.scope;
      credential.tokenType = data.token_type;

      // Verificar se o colaborador já existe, se não existir, criar
      const collaborator = await this.repository.findOne({
        where: { userId: data.user_id }
      });

      if (!collaborator) {
        const newCollaborator = new Collaborator();
        newCollaborator.userId = data.user_id;
        newCollaborator.name = data.name;
        newCollaborator.email = data.email;
        newCollaborator.picture = data.picture;
        await this.repository.save(newCollaborator);
      }

      const savedCredential = await this.credentialRepository.save(credential);

      return savedCredential;
    } catch (error: any) {
      this.logger.error("Erro ao salvar credenciais:", error);
      throw error;
    }
  }

  public async updateUserTokens(email: string, tokens: {
    access_token: string;
    refresh_token?: string;
    expiry_date?: number;
  }): Promise<Credential | null> {
    try {
      const { access_token, refresh_token, expiry_date } = tokens;

      // Validar e sanitizar expiry_date
      const validExpiryDate = this.validateExpiryDate(expiry_date);

      const result = await this.credentialRepository
        .createQueryBuilder()
        .update(Credential)
        .set({
          accessToken: access_token,
          refreshToken: refresh_token,
          expiryDate: validExpiryDate
        })
        .where("email = :email", { email })
        .returning("*")
        .execute();

      if (!result.raw || result.raw.length === 0) {
        throw new Error(`Não foi encontrado registro para o email: ${email}`);
      }

      return result.raw[0];
    } catch (error: any) {
      this.logger.error("Erro ao atualizar tokens do usuário:", error);
      throw error;
    }
  }

  public async getUserTokens(email: string): Promise<Credential | null> {
    try {
      return await this.credentialRepository.findOne({
        where: { email },
        order: { updatedAt: "DESC" }
      });
    } catch (error: any) {
      this.logger.error("Erro ao buscar tokens do usuário:", error);
      throw error;
    }
  }

  public async disableCredential(email: string): Promise<Credential | null> {
    try {
      const credential = await this.credentialRepository.findOne({
        where: { email },
        order: { updatedAt: "DESC" }
      });
      if (!credential) {
        this.logger.warn(`Credenciais não encontradas para o email: ${email}`);
        return null;
      }

      credential.ativo = false;

      return await this.credentialRepository.save({
        ...credential,
      });

    } catch (error: any) {
      this.logger.error("Erro ao desativar credenciais:", error);
      throw error;
    }
  }

  private validateExpiryDate(expiryDate?: number): number {
    // Se for undefined ou null, retorne um valor padrão (1 hora a partir de agora)
    if (expiryDate === undefined || expiryDate === null) {
      this.logger.warn('Data de expiração ausente, usando valor padrão (1 hora)');
      return Date.now() + (3600 * 1000);
    }

    // Se for um valor negativo ou inválido, retorne um valor padrão
    if (isNaN(expiryDate) || expiryDate <= 0) {
      this.logger.warn(`Data de expiração inválida (${expiryDate}), usando valor padrão (1 hora)`);
      return Date.now() + (3600 * 1000);
    }

    return expiryDate;
  }

  public async updateCollaborator(userId: string, data: Partial<Collaborator>): Promise<Collaborator | null> {
    try {
      const collaborator = await this.getCollaboratorById(userId);
      if (!collaborator) {
        this.logger.warn(`Colaborador não encontrado: ${userId}`);
        return null;
      }

      Object.assign(collaborator, data);
      return await this.repository.save(collaborator);
    } catch (error: any) {
      this.logger.error("Erro ao atualizar colaborador:", error);
      throw error;
    }
  }

  public async getCollaboratorByEmail(email: string): Promise<Collaborator | null> {
    try {
      return await this.repository.findOne({ where: { email } });
    } catch (error: any) {
      this.logger.error('Erro ao buscar colaborador por email:', error);
      throw error;
    }
  }

  /**
   * Cria um novo colaborador manualmente (admin)
   */
  public async createCollaborator(data: { name: string; email: string; password: string; isAdmin?: boolean }): Promise<void> {
    try {
      await this.repository.save({
        userId: uuidv4(),
        name: data.name,
        email: data.email,
        password: data.password,
        isAdmin: !!data.isAdmin
      });
      this.logger.info(`Colaborador criado manualmente: ${data.email}`);
    } catch (error: any) {
      this.logger.error('Erro ao criar colaborador manualmente:', error);
      throw error;
    }
  }

  /**
   * Verifica se o usuário tem credencial ativa (Drive conectado)
   */
  public async hasActiveDrive(userId: string): Promise<boolean> {
    try {
      const cred = await this.credentialRepository.findOne({
        where: { userId, ativo: true }
      });
      return !!cred;
    } catch (error: any) {
      this.logger.error('Erro ao verificar drive conectado:', error);
      return false;
    }
  }
}
