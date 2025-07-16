import { AppDataSource } from "./data-source";
import { getDevSeedData } from "../seeds/dev-seed";
import { Collaborator } from '../domain/models/Collaborators';
import bcrypt from 'bcryptjs';
import { ConfigRepository } from './repositories/config-repository';

// export async function initializeDevSeed() {
//   if (process.env.NODE_ENV !== "development") {
//     return;
//   }
//   await seedAdmin();
//   try {
//     const { collaborator, credential } = getDevSeedData();
//     const existingCollaborator = await AppDataSource.getRepository(collaborator.constructor).findOne({
//       where: { userId: collaborator.userId }
//     });
//     if (existingCollaborator) {
//       console.log("ℹ️ Seed já foi executado anteriormente, pulando...");
//       return;
//     }
//     await AppDataSource.getRepository(collaborator.constructor).save(collaborator);
//     console.log("✅ Colaborador criado com sucesso!");
//     await AppDataSource.getRepository(credential.constructor).save(credential);
//     console.log("✅ Credencial criada com sucesso!");
//     console.log("✅ Seed de desenvolvimento concluído com sucesso!");
//   } catch (error) {
//     console.error("❌ Erro ao executar o seed:", error);
//   }
// }

// export async function seedAdmin() {
//   const repo = AppDataSource.getRepository(Collaborator);
//   const adminEmail = 'admin@admin.com';
//   let admin = await repo.findOneBy({ email: adminEmail });
//   if (!admin) {
//     const hashedPassword = await bcrypt.hash('admin123', 10);
//     admin = repo.create({
//       userId: 'admin',
//       name: 'Administrador',
//       email: adminEmail,
//       password: hashedPassword, // Agora salva como hash!
//       isAdmin: true
//     });
//     await repo.save(admin);
//     console.log('Admin padrão criado:', adminEmail);
//   }
// }

import { Logger } from '../utils/logger';

export async function initializeDevSeed() {
  // Configuração de múltiplas pastas
  const logger = new Logger();
  const configRepo = new ConfigRepository(logger);
  await configRepo.setConfig('root_folder', [
    'Meet Recordings',
    'Gravações',
    'https://drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9',
    '1A2B3C4D5E6F7G8H9'
  ]);
}

export async function seedAdmin() {
  // ... existing code ...
} 
