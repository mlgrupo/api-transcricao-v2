import { NextFunction, Request, Response } from 'express';

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