import { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';

export const authMiddleware = async (req: Request, res: Response, next: NextFunction) => {
  const apiKey = process.env.X_API_KEY; // Chave de API configurada no .env
  const apiKeyRequest = req.headers['x-api-key']; // Chave enviada na requisição

  if (!apiKeyRequest) {
    res.status(401).json({ error: 'x-api-key header missing' });
  }

  if (apiKeyRequest !== apiKey) {
    res.status(403).json({ error: 'Invalid API Key' });
  }
  next();
};

export const jwtAuthMiddleware = (req: Request, res: Response, next: NextFunction) => {
  const authHeader = req.headers['authorization'];
  if (!authHeader) {
    return res.status(401).json({ error: 'Token JWT não fornecido.' });
  }
  const token = authHeader.split(' ')[1];
  if (!token) {
    return res.status(401).json({ error: 'Token JWT mal formatado.' });
  }
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'secret');
    // @ts-ignore
    req.user = decoded;
    next();
  } catch {
    return res.status(401).json({ error: 'Token JWT inválido ou expirado.' });
  }
};