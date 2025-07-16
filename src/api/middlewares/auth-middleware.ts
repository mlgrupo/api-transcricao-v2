import { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';

// Estender a interface Request
declare module 'express-serve-static-core' {
  interface Request {
    user?: any;
  }
}

export const authMiddleware = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
  const apiKey = process.env.X_API_KEY;
  const apiKeyRequest = req.headers['x-api-key'];

  if (!apiKeyRequest) {
    res.status(401).json({ error: 'x-api-key header missing' });
    return;
  }

  if (apiKeyRequest !== apiKey) {
    res.status(403).json({ error: 'Invalid API Key' });
    return;
  }
  
  next();
};

export const jwtAuthMiddleware = (req: Request, res: Response, next: NextFunction): void => {
  const authHeader = req.headers['authorization'];
  if (!authHeader) {
    res.status(401).json({ error: 'Token JWT não fornecido.' });
    return;
  }
  
  const token = authHeader.split(' ')[1];
  if (!token) {
    res.status(401).json({ error: 'Token JWT mal formatado.' });
    return;
  }
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'secret');
    req.user = decoded;
    next();
  } catch {
    res.status(401).json({ error: 'Token JWT inválido ou expirado.' });
    return;
  }
};