import { AppDataSource } from "./data-source";
import { getDevSeedData } from "../seeds/dev-seed";

export async function initializeDevSeed() {
  if (process.env.NODE_ENV !== "development") {
    return;
  }

  try {
    const { collaborator, credential } = getDevSeedData();

    // Verifica se o colaborador já existe
    const existingCollaborator = await AppDataSource.getRepository(collaborator.constructor).findOne({
      where: { userId: collaborator.userId }
    });

    if (existingCollaborator) {
      console.log("ℹ️ Seed já foi executado anteriormente, pulando...");
      return;
    }

    // Salva o colaborador
    await AppDataSource.getRepository(collaborator.constructor).save(collaborator);
    console.log("✅ Colaborador criado com sucesso!");

    // Salva a credencial
    await AppDataSource.getRepository(credential.constructor).save(credential);
    console.log("✅ Credencial criada com sucesso!");

    console.log("✅ Seed de desenvolvimento concluído com sucesso!");
  } catch (error) {
    console.error("❌ Erro ao executar o seed:", error);
  }
} 
