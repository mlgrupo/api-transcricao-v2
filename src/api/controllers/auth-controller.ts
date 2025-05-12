import { Request, Response } from "express";
import { GoogleAuthService } from "../../infrastructure/auth/google-auth";
import { CollaboratorService } from "../../domain/services/collaborator-service";
import { Logger } from "../../utils/logger";

export class AuthController {
  constructor(
    private authService: GoogleAuthService,
    private collaboratorService: CollaboratorService,
    private logger: Logger
  ) {}

  public async googleCallback(req: Request, res: Response): Promise<Response> {
    try {
      this.logger.info("Entrou no callback do Google");
      
      const { code } = req.body;
      
      if (!code) {
        this.logger.error("Código de autorização ausente na requisição");
        return res.status(400).json({ error: "Missing code parameter" });
      }

      this.logger.info(`Código de autorização recebido (tamanho: ${code.length} caracteres)`);

      try {
        const { tokens, userInfo } = await this.authService.exchangeCodeForTokens(code);
        
        // Validar domínio do email
        if (!userInfo.email) {
          this.logger.error("Email não retornado pelo Google");
          return res.status(400).json({ error: "Email not returned from Google" });
        }

        const emailDomain = userInfo.email.split('@')[1];
        if (emailDomain !== "reconectaoficial.com.br") {
          this.logger.error(`Domínio de email não autorizado: ${emailDomain}`);
          return res.status(403).json({ 
            error: "Invalid domain",
            message: `O email ${userInfo.email} não pertence ao domínio reconectaoficial.com.br`
          });
        }

        if (!tokens.access_token) {
          this.logger.error("Token de acesso não retornado pelo Google");
          return res.status(500).json({ error: "No access token returned from Google" });
        }

        // Salvar ou atualizar credenciais
        try {
          await this.collaboratorService.saveCredentials({
            name: userInfo.name,
            picture: userInfo.picture,
            user_id: userInfo.id,
            email: userInfo.email,
            access_token: tokens.access_token,
            refresh_token: tokens.refresh_token,
            expiry_date: tokens.expiry_date,
            scope: tokens.scope,
            token_type: tokens.token_type
          });

          this.logger.info(`Autenticação bem-sucedida para: ${userInfo.email}`);
          return res.status(200).json({
            message: "Authentication successful",
            userId: userInfo.id,
            email: userInfo.email,
          });
        } catch (credError: any) {
          // Tratar erros específicos de salvamento de credenciais
          this.logger.error(`Erro ao salvar/atualizar credenciais: ${credError.message}`);
          
          if (credError.message.includes('duplicate key')) {
            // Este erro não deve mais acontecer com a nova implementação,
            // mas mantemos por segurança
            return res.status(409).json({
              error: "Duplicate user",
              message: "O usuário já existe. Tente novamente."
            });
          }
          
          return res.status(500).json({
            error: "Credential storage error",
            message: credError.message
          });
        }
      } catch (error: any) {
        // Verificar erro específico de invalid_grant
        const errorMessage = error.message || '';
        
        if (errorMessage.includes('invalid_grant')) {
          this.logger.error("Erro de invalid_grant ao trocar código por tokens", {
            message: "O código de autorização pode ter expirado ou já foi usado. Por favor, tente autenticar novamente.",
            originalError: errorMessage
          });
          
          return res.status(400).json({
            error: "invalid_grant",
            message: "O código de autorização expirou ou já foi usado. Por favor, tente autenticar novamente."
          });
        }
        
        this.logger.error("Erro ao trocar código por tokens:", error.message);
        return res.status(500).json({
          error: "Token exchange error",
          message: error.message,
        });
      }
    } catch (outerError: any) {
      this.logger.error(`Erro não tratado no callback do Google: ${outerError.message}`, {
        stack: outerError.stack
      });
      return res.status(500).json({
        error: "Unhandled error in Google callback",
        message: outerError.message,
      });
    }
  }
}
