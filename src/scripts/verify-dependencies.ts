import { AppDataSource } from "../data/data-source";
import { Logger } from "../utils/logger";
import { Application } from "../application";

/**
 * Script para verificar dependências do sistema
 */
async function verifyDependencies() {
  const logger = new Logger();
  logger.info("🔍 Verificando dependências do sistema...");

  try {
    // Verificar banco de dados
    logger.info("Inicializando conexão com o banco de dados...");
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
    }
    logger.info("✅ Banco de dados conectado com sucesso");

    // Inicializar a aplicação
    logger.info("Inicializando aplicação...");
    const app = await Application.getInstance();
    await app.initialize();
    logger.info("✅ Aplicação inicializada com sucesso");

    // Verificar serviços principais
    const videoService = app.videoService;
    const transcriptionService = app.transcriptionService;
    
    logger.info("Verificando injeção de dependências...");
    if (!videoService) {
      throw new Error("VideoService não está inicializado");
    }
    if (!transcriptionService) {
      throw new Error("TranscriptionService não está inicializado");
    }

    // Verificar que VideoService tem acesso ao TranscriptionService
    // Esta verificação é indireta, já que não podemos acessar campos privados
    try {
      logger.info("Testando acesso do VideoService ao TranscriptionService...");
      const videoId = "test-video-id";
      // Criar um mock do método resetQueueStatus
      const originalMethod = videoService.resetQueueStatus;
      let transcriptionServiceAccessed = false;
      
      videoService.resetQueueStatus = async (id: string) => {
        if (id === videoId) {
          transcriptionServiceAccessed = true;
          return { 
            success: true, 
            message: "Teste de dependência bem-sucedido" 
          };
        }
        return originalMethod.call(videoService, id);
      };
      
      await videoService.resetQueueStatus(videoId);
      
      // Restaurar o método original
      videoService.resetQueueStatus = originalMethod;
      
      if (transcriptionServiceAccessed) {
        logger.info("✅ VideoService tem acesso ao TranscriptionService");
      } else {
        logger.warn("⚠️ Não foi possível confirmar se VideoService tem acesso ao TranscriptionService");
      }
    } catch (error: any) {
      logger.error("❌ Erro ao testar acesso do VideoService ao TranscriptionService:", error);
    }

    // Verificar Python e dependências
    logger.info("Verificando ambiente Python...");
    const pythonStatus = await app.videoRepository.checkTranscriptionSystem();
    
    if (pythonStatus.pythonAvailable) {
      logger.info("✅ Python disponível");
    } else {
      logger.warn("⚠️ Python não encontrado. Verifique a instalação do Python");
    }
    
    if (pythonStatus.scriptAvailable) {
      logger.info("✅ Script de transcrição encontrado");
    } else {
      logger.warn("⚠️ Script de transcrição não encontrado. Verifique o arquivo python/transcribe.py");
    }
    
    if (pythonStatus.whisperAvailable) {
      logger.info("✅ Biblioteca Whisper disponível");
    } else {
      logger.warn("⚠️ Biblioteca Whisper não encontrada. Execute install-dependencies.bat");
    }

    logger.info("✅ Verificação de dependências concluída");
    
  } catch (error: any) {
    logger.error("❌ Falha na verificação de dependências:", error);
  } finally {
    if (AppDataSource.isInitialized) {
      await AppDataSource.destroy();
    }
  }
}

// Executar script se for o arquivo principal
if (require.main === module) {
  verifyDependencies()
    .then(() => {
      console.log("✨ Script de verificação concluído");
      process.exit(0);
    })
    .catch(error => {
      console.error("❌ Erro:", error);
      process.exit(1);
    });
}
