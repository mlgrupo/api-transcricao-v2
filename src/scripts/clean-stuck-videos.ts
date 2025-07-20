import { AppDataSource } from "../data/data-source";
import { Logger } from "../utils/logger";
import { VideoRepository } from "../data/repositories/video-repository";

/**
 * Script para limpar vídeos travados em processamento
 */
async function cleanStuckVideos() {
  const logger = new Logger();
  logger.info("🧹 Iniciando limpeza de vídeos travados...");

  try {
    // Inicializar banco de dados
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
    }

    const videoRepository = new VideoRepository(logger);

    // Buscar vídeos em processamento há mais de 2 horas
    const twoHoursAgo = new Date();
    twoHoursAgo.setHours(twoHoursAgo.getHours() - 2);

    // Usar query builder diretamente do AppDataSource
    const stuckVideos = await AppDataSource.createQueryBuilder()
      .select("video")
      .from("transcricao_v2.videos_mapeados", "video")
      .where("video.status = :status", { status: "processing" })
      .andWhere("video.dt_atualizacao < :twoHoursAgo", { twoHoursAgo })
      .getMany();

    logger.info(`Encontrados ${stuckVideos.length} vídeos travados`);

    for (const video of stuckVideos) {
      try {
        // Resetar status para permitir reprocessamento
        await AppDataSource.createQueryBuilder()
          .update("transcricao_v2.videos_mapeados")
          .set({
            status: "pending",
            enfileirado: false,
            progress: 0,
            etapa_atual: "Aguardando reprocessamento",
            dt_atualizacao: new Date()
          })
          .where("video_id = :videoId", { videoId: video.video_id })
          .execute();

        logger.info(`✅ Vídeo ${video.video_id} resetado para reprocessamento`);
      } catch (error: any) {
        logger.error(`❌ Erro ao resetar vídeo ${video.video_id}:`, error.message);
      }
    }

    logger.info("🧹 Limpeza de vídeos travados concluída");
  } catch (error: any) {
    logger.error("❌ Erro na limpeza de vídeos travados:", error);
    process.exit(1);
  }
}

// Executar script se for o arquivo principal
if (require.main === module) {
  cleanStuckVideos()
    .then(() => {
      console.log("✨ Script de limpeza concluído");
      process.exit(0);
    })
    .catch(error => {
      console.error("❌ Erro:", error);
      process.exit(1);
    });
} 