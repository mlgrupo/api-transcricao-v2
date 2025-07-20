import { AppDataSource } from "../data/data-source";
import { Logger } from "../utils/logger";
import { VideoRepository } from "../data/repositories/video-repository";

/**
 * Script para reiniciar vídeos que falharam na transcrição
 */
async function restartFailedTranscriptions() {
  const logger = new Logger();
  logger.info("🔄 Iniciando reinicialização de transcrições falhadas...");

  try {
    // Inicializar banco de dados
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
    }

    const videoRepository = new VideoRepository(logger);

    // Buscar vídeos com erro na transcrição
    const failedVideos = await AppDataSource
      .createQueryBuilder("video", "v")
      .where("v.transcrito = :status", { status: "ERRO" })
      .orWhere("v.transcrito IS NULL AND v.etapaAtual = :progresso", { progresso: "Iniciando transcrição do vídeo" })
      .getMany();

    logger.info(`Encontrados ${failedVideos.length} vídeos com falha na transcrição`);

    if (failedVideos.length === 0) {
      logger.info("✅ Nenhum vídeo com falha encontrado");
      return;
    }

    // Resetar status dos vídeos falhados
    for (const video of failedVideos) {
      logger.info(`🔄 Resetando vídeo: ${video.id} (${video.nome})`);
      
      await AppDataSource
        .createQueryBuilder()
        .update("transcricao_v2.videos_mapeados")
        .set({
          transcrito: null,
          etapaAtual: "Aguardando processamento",
          progress: 0,
          dtAtualizacao: new Date()
        })
        .where("id = :id", { id: video.id })
        .execute();
    }

    logger.info(`✅ ${failedVideos.length} vídeos resetados com sucesso`);
    logger.info("🔄 Os vídeos serão reprocessados automaticamente pelo sistema");

  } catch (error: any) {
    logger.error("❌ Erro ao reiniciar transcrições:", error);
    throw error;
  } finally {
    if (AppDataSource.isInitialized) {
      await AppDataSource.destroy();
    }
  }
}

// Executar se chamado diretamente
if (require.main === module) {
  restartFailedTranscriptions()
    .then(() => {
      console.log("✅ Script concluído com sucesso");
      process.exit(0);
    })
    .catch((error) => {
      console.error("❌ Erro no script:", error);
      process.exit(1);
    });
}

export { restartFailedTranscriptions }; 