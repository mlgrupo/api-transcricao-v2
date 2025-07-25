import fs from 'fs/promises';
import path from 'path';
import ffmpeg from 'fluent-ffmpeg';
import { Logger } from '../../utils/logger';

export class AudioProcessor {
  constructor(private logger: Logger) {}

  public async convertToMp3(videoPath: string, audioPath: string, cancelObj?: { cancelled: boolean }): Promise<string> {
    try {
      this.logger.info('Iniciando conversão para MP3 via fluent‑ffmpeg...', { videoPath, audioPath });
      
      // Verificar se o arquivo de vídeo existe
      const videoExists = await fs.access(videoPath).then(() => true).catch(() => false);
      if (!videoExists) {
        throw new Error(`Arquivo de vídeo não encontrado: ${videoPath}`);
      }
      
      // Criar o diretório onde ficará o arquivo de áudio
      const audioDir = path.dirname(audioPath);
      await fs.mkdir(audioDir, { recursive: true });
      
      // Usar fluent‑ffmpeg para converter o vídeo para MP3
      await new Promise<void>((resolve, reject) => {
        const proc = ffmpeg(videoPath)
          .noVideo()
          .audioCodec('libmp3lame')
          .audioBitrate('128k')
          .output(audioPath)
          .on('end', () => {
            clearInterval(interval);
            resolve();
          })
          .on('error', (err) => {
            clearInterval(interval);
            reject(err);
          });
        // Checar cancelamento periodicamente
        const interval = setInterval(() => {
          if (cancelObj?.cancelled && (proc as any).ffmpegProc) {
            (proc as any).ffmpegProc.kill('SIGKILL');
            clearInterval(interval);
            this.logger.info('Conversão para MP3 cancelada pelo usuário', { videoPath });
            reject(new Error('Conversão para MP3 cancelada pelo usuário'));
          }
        }, 300);
        proc.run();
      });
      
      // Verificar se o arquivo MP3 foi gerado
      const audioExists = await fs.access(audioPath).then(() => true).catch(() => false);
      if (!audioExists) {
        throw new Error('Arquivo MP3 não foi gerado');
      }
      
      const stats = await fs.stat(audioPath);
      if (stats.size === 0) {
        throw new Error('Arquivo MP3 gerado está vazio');
      }
      
      this.logger.info('Conversão para MP3 concluída', { videoPath, audioPath, size: stats.size });
      return audioPath;
    } catch (error: any) {
      this.logger.error('Erro na conversão para MP3:', {
        error: error.message,
        videoPath,
        audioPath
      });
      // Se cancelado, remover arquivo parcial
      if (cancelObj?.cancelled) {
        try { await fs.unlink(audioPath); } catch {}
      }
      throw new Error(`Erro na conversão para MP3: ${error.message}`);
    }
  }
  public async cleanup(...files: string[]): Promise<void> {
    for (const file of files) {
      try {
        await fs.unlink(file);
        this.logger.info('Arquivo deletado', { file });
      } catch (error: any) {
        if (error.code !== 'ENOENT') {
          this.logger.error('Erro ao remover arquivo', { file, error: error.message });
          throw error;
        }
      }
    }
  }
}
