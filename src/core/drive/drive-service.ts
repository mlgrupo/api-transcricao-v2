import fs from 'fs/promises';
import { createWriteStream } from 'fs';
import path from 'path';
import { Logger } from '../../utils/logger';
import { IDriveService } from './interfaces/IDriveResources';

interface findedFolder {
  folderId: string;
  name: string;
  mimeType: string;
  parentFolderId: string;
}

export class DriveService implements IDriveService {
  constructor(private logger: Logger) { }

  public async downloadVideo(drive: any, videoId: string, outputPath: string): Promise<void> {
    try {
      this.logger.info('Iniciando download de vídeo do Google Drive', { videoId, outputPath });
      const dir = path.dirname(outputPath);
      await fs.mkdir(dir, { recursive: true });

      const fileMetadataResponse = await drive.files.get({
        fileId: videoId,
        fields: 'size,name,mimeType'
      });

      if (!fileMetadataResponse.data) {
        throw new Error('Não foi possível obter metadados do arquivo');
      }

      const { size, name } = fileMetadataResponse.data;
      if (!size || size === '0') {
        throw new Error(`Arquivo vazio no Google Drive: ${name} (${videoId})`);
      }

      const dest = createWriteStream(outputPath, { mode: 0o666 });
      let attempts = 0;
      const maxAttempts = 3;

      while (attempts < maxAttempts) {
        attempts++;
        try {
          this.logger.info(`Tentativa de download ${attempts}/${maxAttempts}`, { videoId });
          const response = await drive.files.get(
            { fileId: videoId, alt: 'media' },
            { responseType: 'stream' }
          );

          if (!response.data) {
            throw new Error('Resposta vazia do Google Drive');
          }

          let fileSize = parseInt(response.headers['content-length'] || size || '0', 10);
          if (fileSize === 0 && size) {
            fileSize = parseInt(size, 10);
            this.logger.info('Usando tamanho dos metadados para o progresso', { size });
          }
          if (fileSize === 0) {
            throw new Error('Não foi possível determinar o tamanho do arquivo');
          }

          let downloadedBytes = 0;
          let lastLoggedPercent = 0;

          await new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => {
              reject(new Error('Timeout de download excedido'));
            }, 40 * 60 * 1000); // timeout ajustado para 40 minutos

            response.data
              .on('data', (chunk: Buffer) => {
                downloadedBytes += chunk.length;
                const percent = Math.round((downloadedBytes / fileSize) * 100);
                if (percent >= lastLoggedPercent + 5) {
                  this.logger.info(`Download progresso: ${percent}%`, { videoId, downloadedBytes, totalBytes: fileSize });
                  lastLoggedPercent = percent;
                }
              })
              .on('end', async () => {
                clearTimeout(timeout);
                this.logger.info('Download concluído', { videoId, totalBytes: fileSize });
                try {
                  const stats = await fs.stat(outputPath);
                  if (stats.size === 0) throw new Error('Arquivo baixado está vazio');
                  this.logger.info('Arquivo salvo com sucesso', { videoId, size: stats.size });
                  resolve();
                } catch (err: any) {
                  this.logger.error('Erro ao verificar arquivo baixado:', { error: err.message, path: outputPath });
                  reject(err);
                }
              })
              .on('error', (error: Error) => {
                clearTimeout(timeout);
                this.logger.error('Erro durante o download:', { error: error.message, videoId });
                reject(error);
              });

            dest.on('error', (error: Error) => {
              clearTimeout(timeout);
              this.logger.error('Erro ao escrever arquivo:', { error: error.message, path: outputPath });
              reject(error);
            });

            response.data.pipe(dest);
          });
          return;
        } catch (error: any) {
          this.logger.error(`Erro na tentativa ${attempts}/${maxAttempts} de download:`, { error: error.message, videoId });
          if (attempts >= maxAttempts) throw error;
          await new Promise(resolve => setTimeout(resolve, 5000));
        }
      }
    } catch (error: any) {
      this.logger.error('Erro fatal no download de vídeo:', { error: error.message, stack: error.stack, videoId, outputPath });
      throw error;
    }
  }

  public async createFolder(drive: any, folderName: string, parentFolderId?: string): Promise<string> {
    try {
      this.logger.info(`Criando pasta no Google Drive: ${folderName}`, { parentFolderId });
      const driveFolderResponse = await drive.files.create({
        requestBody: {
          name: folderName,
          mimeType: 'application/vnd.google-apps.folder',
          parents: [parentFolderId],
        },
        fields: 'id',
      });
      const folderId = driveFolderResponse.data.id;
      this.logger.info('Pasta criada no Google Drive', { folderId });
      return folderId;
    } catch (error: any) {
      this.logger.error('Erro ao criar pasta no Google Drive:', { error: error.message });
      throw error;
    }
  }

  public async moveFile(drive: any, fileId: string, addParents: string, removeParents: string): Promise<void> {
    try {
      this.logger.info('Movendo arquivo no Google Drive', { fileId, addParents, removeParents });
      const result = await drive.files.update({
        fileId,
        addParents,
        removeParents,
        fields: 'id, parents',
      });

      if (!result.data) {
        throw new Error('Não foi possível mover o arquivo');
      }
      this.logger.info('Arquivo movido com sucesso', { fileId });
    } catch (error: any) {
      this.logger.error('Erro ao mover arquivo no Google Drive:', { error: error.message, fileId });
      throw error;
    }
  }

  public async uploadFile(drive: any, folderId: string, filename: string, mimeType: string, bodyContent: string): Promise<void> {
    try {
      this.logger.info('Enviando arquivo para o Google Drive', { filename, folderId });
      await drive.files.create({
        requestBody: {
          name: filename,
          parents: [folderId],
          mimeType
        },
        media: {
          mimeType,
          body: bodyContent
        }
      });
      this.logger.info('Arquivo enviado com sucesso', { filename });
    } catch (error: any) {
      this.logger.error('Erro ao enviar arquivo para o Google Drive:', { error: error.message });
      throw error;
    }
  }

  // esse metodo não é usado para criação de pastas, apenas verificação se a pasta existe
  public async checkFolderHasCreated(folderName: string, drive: any, parentFolderId?: string): Promise<findedFolder | null> {
    try {
      this.logger.info('Verificando se a pasta existe no Google Drive', { folderName, parentFolderId });

      let query = `name='${folderName}' and mimeType='application/vnd.google-apps.folder' and trashed = false`;
      if (parentFolderId) {
        query += ` and '${parentFolderId}' in parents`;
      }

      const folderRes = await drive.files.list({
        q: query,
        fields: 'files(id, name, mimeType, createdTime, modifiedTime, parents)',
        spaces: 'drive',
      });

      if (!folderRes.data.files || folderRes.data.files.length === 0) {
        this.logger.warn(`Pasta '${folderName}' não encontrada`, { parentFolderId });
        return null;
      }

      this.logger.info(`Pasta '${folderName}' encontrada`);
      return {
        folderId: folderRes.data.files[0].id,
        name: folderRes.data.files[0].name,
        mimeType: folderRes.data.files[0].mimeType,
        parentFolderId: folderRes.data.files[0].parents ? folderRes.data.files[0].parents[0] : null,
      }

    } catch (error: any) {
      this.logger.error('Erro ao verificar pasta no Google Drive:', { error: error.message, folderName, parentFolderId });
      throw error;
    }
  }

  public async getFileById (drive: any, fileId: string): Promise<findedFolder | null> {
    try {
      this.logger.info('Verificando se o arquivo existe no Google Drive', { fileId });
      const fileRes = await drive.files.get({ fileId, fields: 'id, name, mimeType, createdTime, modifiedTime, parents' });

      if (!fileRes.data) {
        this.logger.warn(`Arquivo '${fileId}' não encontrado`, { fileId });
        return null;
      }
      
      return {
        folderId: fileRes.data.id,
        name: fileRes.data.name,
        mimeType: fileRes.data.mimeType,
        parentFolderId: fileRes.data.parents ? fileRes.data.parents[0] : null,
      };

    } catch (error: any) {
      this.logger.error('Erro ao verificar arquivo no Google Drive:', { error: error.message, fileId });
      throw error;
    }
  }
}
