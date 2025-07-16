import { Request, Response, NextFunction, RequestHandler } from 'express';

type AsyncFunction = (req: Request, res: Response, next: NextFunction) => Promise<any> | any;

export default function asyncHandler(fn: AsyncFunction): RequestHandler {
  return (req: Request, res: Response, next: NextFunction): void => {
    const result = fn(req, res, next);
    if (result && typeof result.catch === 'function') {
      result.catch(next);
    }
  };
}