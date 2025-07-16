import { Request, Response, NextFunction } from "express";
import { GoogleAuthService } from "../../infrastructure/auth/google-auth";
import { CollaboratorService } from "../../domain/services/collaborator-service";
import { Logger } from "../../utils/logger";
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';

export class AuthController {
  constructor(
    private authService: GoogleAuthService,
    private collaboratorService: CollaboratorService,
    private logger: Logger
  ) {}

  public async googleCallback(req: Request, res: Response): Promise<void> {
    try {
      this.logger.info("Entrou no callback do Google");
      
      const { code } = req.body;
      
      if (!code) {
        this.logger.error("Código de autorização ausente na requisição");
        res.status(400).json({ error: "Missing code parameter" });
        return;
      }

      this.logger.info(`Código de autorização recebido (tamanho: ${code.length} caracteres)`);

      try {
        const { tokens, userInfo } = await this.authService.exchangeCodeForTokens(code);
        
        // Validar domínio do email
        if (!userInfo.email) {
          this.logger.error("Email não retornado pelo Google");
          res.status(400).json({ error: "Email not returned from Google" });
          return;
        }

        const emailDomain = userInfo.email.split('@')[1];
        if (emailDomain !== "reconectaoficial.com.br") {
          this.logger.error(`Domínio de email não autorizado: ${emailDomain}`);
          res.status(403).json({ 
            error: "Invalid domain",
            message: `O email ${userInfo.email} não pertence ao domínio reconectaoficial.com.br`
          });
          return;
        }

        if (!tokens.access_token) {
          this.logger.error("Token de acesso não retornado pelo Google");
          res.status(500).json({ error: "No access token returned from Google" });
          return;
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

          // Buscar colaborador para pegar isAdmin
          const collaborator = await this.collaboratorService.getCollaboratorByEmail(userInfo.email);
          const isAdmin = collaborator?.isAdmin || false;

          // Gerar JWT igual ao login tradicional
          const token = jwt.sign(
            {
              userId: userInfo.id,
              email: userInfo.email,
              name: userInfo.name,
              isAdmin,
              picture: userInfo.picture,
            },
            process.env.JWT_SECRET || 'secret',
            { expiresIn: '12h' }
          );

          this.logger.info(`Autenticação bem-sucedida para: ${userInfo.email}`);
          res.status(200).json({
            token,
            user: {
              userId: userInfo.id,
              name: userInfo.name,
              email: userInfo.email,
              isAdmin,
              picture: userInfo.picture,
            }
          });
          return;
        } catch (credError: any) {
          // Tratar erros específicos de salvamento de credenciais
          this.logger.error(`Erro ao salvar/atualizar credenciais: ${credError.message}`);
          
          if (credError.message.includes('duplicate key')) {
            // Este erro não deve mais acontecer com a nova implementação,
            // mas mantemos por segurança
            res.status(409).json({
              error: "Duplicate user",
              message: "O usuário já existe. Tente novamente."
            });
            return;
          }
          
          res.status(500).json({
            error: "Credential storage error",
            message: credError.message
          });
          return;
        }
      } catch (error: any) {
        // Verificar erro específico de invalid_grant
        const errorMessage = error.message || '';
        
        if (errorMessage.includes('invalid_grant')) {
          this.logger.error("Erro de invalid_grant ao trocar código por tokens", {
            message: "O código de autorização pode ter expirado ou já foi usado. Por favor, tente autenticar novamente.",
            originalError: errorMessage
          });
          
          res.status(400).json({
            error: "invalid_grant",
            message: "O código de autorização expirou ou já foi usado. Por favor, tente autenticar novamente."
          });
          return;
        }
        
        this.logger.error("Erro ao trocar código por tokens:", error.message);
        res.status(500).json({
          error: "Token exchange error",
          message: error.message,
        });
        return;
      }
    } catch (outerError: any) {
      this.logger.error(`Erro não tratado no callback do Google: ${outerError.message}`, {
        stack: outerError.stack
      });
      res.status(500).json({
        error: "Unhandled error in Google callback",
        message: outerError.message,
      });
    }
  }

  public async login(req: Request, res: Response): Promise<void> {
    try {
      const { email, password } = req.body;
      if (!email || !password) {
        res.status(400).json({ error: 'Email e senha são obrigatórios.' });
        return;
      }
      // Buscar colaborador pelo email
      const collaborator = await this.collaboratorService.getCollaboratorByEmail(email);
      if (!collaborator || !collaborator.password) {
        res.status(401).json({ error: 'Usuário ou senha inválidos.' });
        return;
      }
      // Validar senha
      const valid = await bcrypt.compare(password, collaborator.password);
      if (!valid) {
        res.status(401).json({ error: 'Usuário ou senha inválidos.' });
        return;
      }
      // Gerar JWT
      const token = jwt.sign(
        {
          userId: collaborator.userId,
          email: collaborator.email,
          name: collaborator.name,
          isAdmin: collaborator.isAdmin,
        },
        process.env.JWT_SECRET || 'secret',
        { expiresIn: '12h' }
      );
      res.status(200).json({
        token,
        user: {
          userId: collaborator.userId,
          name: collaborator.name,
          email: collaborator.email,
          isAdmin: collaborator.isAdmin,
          picture: collaborator.picture,
        }
      });
    } catch (error: any) {
      this.logger.error('Erro no login tradicional:', error.message);
      res.status(500).json({ error: 'Erro interno ao fazer login.' });
    }
  }

  public async createUser(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const user = req.user as any;
      if (!user || !user.isAdmin) {
        res.status(403).json({ error: 'Acesso negado. Apenas administradores podem criar usuários.' });
        return;
      }
      const { name, email, password, isAdmin } = req.body;
      if (!name || !email || !password) {
        res.status(400).json({ error: 'Nome, email e senha são obrigatórios.' });
        return;
      }
      // Verifica se já existe usuário com esse email
      const existing = await this.collaboratorService.getCollaboratorByEmail(email);
      if (existing) {
        res.status(409).json({ error: 'Já existe um usuário com esse email.' });
        return;
      }
      // Cria o usuário
      await this.collaboratorService.createCollaborator({
        name,
        email,
        password,
        isAdmin: !!isAdmin
      });
      res.status(201).json({ message: 'Usuário criado com sucesso.' });
    } catch (error: any) {
      this.logger.error('Erro ao criar usuário:', error.message);
      res.status(500).json({ error: 'Erro interno ao criar usuário.' });
    }
  }

  // Adicionar método para retornar dados do usuário autenticado com driveConnected
  public static async getMe(req: Request, res: Response) {
    try {
      // @ts-ignore
      const user = req.user;
      if (!user) return res.status(401).json({ error: 'Não autenticado.' });
      // Buscar colaborador completo
      const collaboratorService = req.app.get('collaboratorService');
      const collaborator = await collaboratorService.getCollaboratorByEmail(user.email);
      if (!collaborator) return res.status(404).json({ error: 'Usuário não encontrado.' });
      // Retornar dados com driveConnected
      return res.status(200).json({
        userId: collaborator.userId,
        name: collaborator.name,
        email: collaborator.email,
        isAdmin: collaborator.isAdmin,
        picture: collaborator.picture,
        driveConnected: collaborator.driveConnected || false
      });
    } catch (error: any) {
      return res.status(500).json({ error: 'Erro ao buscar usuário.' });
    }
  }
}
