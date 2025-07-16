import { OAuth2Client } from "google-auth-library";
import { google } from "googleapis";
import { Credential } from "../../domain/models/Credentials";
import { Logger } from "../../utils/logger";
import { CollaboratorRepository } from "../../data/repositories/collaborator-repository";

export class TokenManager {
  constructor(
    private collaboratorRepository: CollaboratorRepository,
    private logger: Logger
  ) {}

  public createOAuth2Client(accessToken: string, refreshToken?: string): OAuth2Client {
    const oauth2Client = new google.auth.OAuth2(
      process.env.GOOGLE_CLIENT_ID,
      process.env.GOOGLE_CLIENT_SECRET,
      process.env.REDIRECT_URI
    );

    oauth2Client.setCredentials({
      access_token: accessToken,
      refresh_token: refreshToken,
    });

    return oauth2Client;
  }

  public async handleTokenUpdate(
    userEmail: string,
    currentTokens: Credential,
    updatedTokens: {
      access_token?: string;
      refresh_token?: string;
      expiry_date?: number;
      id_token?: string;
      token_type?: string;
      scope?: string;
      expires_in?: number;
    }
  ): Promise<void> {
    try {
      const newTokens = {
        ...currentTokens,
        ...updatedTokens,
      };

      if (updatedTokens.access_token && updatedTokens.expires_in) {
        const expiresInMs = parseInt(String(updatedTokens.expires_in), 10) * 1000;
        
        if (!isNaN(expiresInMs)) {
          newTokens.expiryDate = Date.now() + expiresInMs;
        } else {
          newTokens.expiryDate = Date.now() + (3600 * 1000);
          this.logger.warn('Valor inválido para expires_in, usando padrão de 1 hora', {
            userEmail,
            expiresIn: updatedTokens.expires_in
          });
        }
      }

      await this.collaboratorRepository.updateUserTokens(userEmail, {
        access_token: updatedTokens.access_token || currentTokens.accessToken,
        refresh_token: updatedTokens.refresh_token || currentTokens.refreshToken,
        expiry_date: newTokens.expiryDate
      });
    } catch (error: any) {
      this.logger.error('Erro ao atualizar tokens do usuário:', {
        error: error.message,
        stack: error.stack,
        userEmail
      });
    }
  }

  public async refreshTokenIfNeeded(userEmail: string): Promise<boolean> {
    try {
      const tokens = await this.collaboratorRepository.getUserTokens(userEmail);
      
      if (!tokens) {
        this.logger.error(`Tokens não encontrados para ${userEmail}`);
        return false;
      }

      const isExpired = tokens.expiryDate && Date.now() > tokens.expiryDate;
      
      if (isExpired) {
        if (!tokens.refreshToken) {
          this.logger.error(`Refresh token não encontrado para ${userEmail} - usuário precisa reconectar`);
          return false;
        }

        this.logger.info(`Token expirado para ${userEmail}, tentando renovar...`);
        
        try {
          const oauth2Client = this.createOAuth2Client("", tokens.refreshToken);
          const { credentials } = await oauth2Client.refreshAccessToken();
          
          if (!credentials.access_token) {
            this.logger.error(`Falha ao renovar token para ${userEmail} - sem access_token retornado`);
            return false;
          }
          
          await this.collaboratorRepository.updateUserTokens(userEmail, {
            access_token: credentials.access_token,
            refresh_token: credentials.refresh_token || tokens.refreshToken,
            expiry_date: credentials.expiry_date ?? Date.now() + (3600 * 1000) // Default to 1 hour if null
          });
          
          this.logger.info(`Token renovado com sucesso para ${userEmail}`);
          return true;
        } catch (refreshError: any) {
          this.logger.error(`Erro ao renovar token para ${userEmail}:`, {
            error: refreshError.message,
            code: refreshError.code,
            status: refreshError.status
          });
          
          // Se o refresh token também expirou, marcar como inválido
          if (refreshError.code === 400 || refreshError.status === 400) {
            this.logger.error(`Refresh token inválido para ${userEmail} - usuário precisa reconectar`);
            return false;
          }
          
          return false;
        }
      }
      
      return true;
    } catch (error: any) {
      this.logger.error(`Erro ao renovar token para ${userEmail}:`, error);
      return false;
    }
  }
}