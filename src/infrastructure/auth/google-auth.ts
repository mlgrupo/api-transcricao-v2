import { google } from "googleapis";
import { OAuth2Client } from "google-auth-library";
import { Logger } from "../../utils/logger";

interface GoogleUserInfo {
  id: string;
  email: string;
  name: string;
  picture?: string;
  hd?: string; // hosted domain
}

export class GoogleAuthService {
  private oauth2Client: OAuth2Client;

  constructor(private logger: Logger) {
    const clientId = process.env.GOOGLE_CLIENT_ID;
    const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
    const redirectUri = process.env.REDIRECT_URI;
    
    if (!clientId || !clientSecret || !redirectUri) {
      this.logger.error("Configurações do OAuth incompletas", {
        clientId: !!clientId,
        clientSecret: !!clientSecret,
        redirectUri: !!redirectUri
      });
    }
    
    this.oauth2Client = new google.auth.OAuth2(
      clientId,
      clientSecret,
      redirectUri
    );
  }

  public async exchangeCodeForTokens(code: string): Promise<{
    tokens: {
      access_token?: string;
      refresh_token?: string;
      expiry_date?: number;
      token_type?: string;
      scope?: string;
    };
    userInfo: GoogleUserInfo;
  }> {
    try {
      this.logger.info("Iniciando troca de código por tokens");
      
      // Trocar código por tokens
      const { tokens } = await this.oauth2Client.getToken(code);
      
      if (!tokens.access_token) {
        throw new Error("No access token returned from Google");
      }
      
      this.logger.info("Tokens obtidos com sucesso", {
        hasAccessToken: !!tokens.access_token,
        hasRefreshToken: !!tokens.refresh_token,
        hasExpiryDate: !!tokens.expiry_date
      });

      // Configurar oauth client com os tokens obtidos
      this.oauth2Client.setCredentials(tokens);

      // Buscar informações do usuário
      const oauth2 = google.oauth2({ auth: this.oauth2Client, version: "v2" });
      const userinfoResponse = await oauth2.userinfo.get();
      const userInfo = userinfoResponse.data as GoogleUserInfo;
      
      this.logger.info("Informações do usuário obtidas", {
        email: userInfo.email,
        domain: userInfo.hd,
        name: userInfo.name
      });

      // Convert any null values to undefined to match the return type
      const sanitizedTokens = {
        access_token: tokens.access_token || undefined,
        refresh_token: tokens.refresh_token || undefined,
        expiry_date: tokens.expiry_date || undefined,
        token_type: tokens.token_type || undefined,
        scope: tokens.scope || undefined
      };

      return { tokens: sanitizedTokens, userInfo };
    } catch (error: any) {
      // Melhorar o log de erros
      const errorMessage = error.message || "Unknown error";
      const errorResponse = error.response?.data || {};
      
      this.logger.error("Erro ao trocar código por tokens", {
        error: errorMessage,
        details: errorResponse,
        code: error.code
      });
      
      throw error;
    }
  }

  public createOAuth2Client(accessToken?: string, refreshToken?: string): OAuth2Client {
    const oauth2Client = new google.auth.OAuth2(
      process.env.GOOGLE_CLIENT_ID,
      process.env.GOOGLE_CLIENT_SECRET,
      process.env.REDIRECT_URI
    );

    if (accessToken) {
      const credentials: {
        access_token: string;
        refresh_token?: string;
      } = { access_token: accessToken };
      
      if (refreshToken) {
        credentials.refresh_token = refreshToken;
      }
      
      oauth2Client.setCredentials(credentials);
    }

    return oauth2Client;
  }
  
  public getAuthUrl(scopes: string[] = []): string {
    const defaultScopes = [
      'https://www.googleapis.com/auth/userinfo.email',
      'https://www.googleapis.com/auth/userinfo.profile',
      'https://www.googleapis.com/auth/drive'
    ];
    
    const finalScopes = scopes.length > 0 ? scopes : defaultScopes;
    
    return this.oauth2Client.generateAuthUrl({
      access_type: 'offline',
      scope: finalScopes,
      prompt: 'consent',  // Force to always show consent screen to get refresh token
      include_granted_scopes: true
    });
  }
}