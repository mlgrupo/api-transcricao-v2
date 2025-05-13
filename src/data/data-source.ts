import { DataSource } from "typeorm";
import { Collaborator } from "../domain/models/Collaborators";
import { Video } from "../domain/models/Video";
import { Credential } from "../domain/models/Credentials";
import { ApplicationLog } from "../domain/models/ApplicationLog"; // Importar a entidade ApplicationLog
import { initializeDevSeed } from "./seed-manager";
import dotenv from 'dotenv';

const envFile = `.env.${process.env.NODE_ENV ?? 'development'}`;

dotenv.config({ path: envFile });
// Garantir que todas as variáveis de ambiente necessárias estejam definidas
const requiredEnvVars = {
  DB_HOST: process.env.DB_HOST,
  DB_PORT: parseInt(process.env.DB_PORT ?? "5432"),
  DB_USERNAME: process.env.DB_USERNAME,
  DB_PASSWORD: String(process.env.DB_PASSWORD), // Forçar conversão para string
  DB_DATABASE: process.env.DB_DATABASE
};

console.log('requiredEnvVars', requiredEnvVars);

// Verificar se a senha está definida
if (!requiredEnvVars.DB_PASSWORD) {
  console.error("❌ Erro: DB_PASSWORD não está definida nas variáveis de ambiente");
  process.exit(1);
}

export const AppDataSource = new DataSource({
  type: "postgres",
  host: requiredEnvVars.DB_HOST,
  port: requiredEnvVars.DB_PORT,
  username: requiredEnvVars.DB_USERNAME,
  password: requiredEnvVars.DB_PASSWORD,
  database: requiredEnvVars.DB_DATABASE,
  synchronize: true, // Ativar temporariamente para criar tabelas automaticamente
  logging: process.env.NODE_ENV === "development",
  entities: [
    Video,
    Collaborator,
    Credential,
    ApplicationLog,
  ],
  migrations: ["src/migrations/**/*.ts"],
  subscribers: ["src/subscribers/**/*.ts"]
});

AppDataSource.initialize()
  .then(async () => {
    console.log('✅ DataSource inicializado com sucesso.');
    
    // Inicializa o seed em ambiente de desenvolvimento
    await initializeDevSeed();
  })
  .catch((error) => {
    console.error('❌ Erro ao inicializar o DataSource:', error);
    process.exit(1); // Finaliza o processo se o DataSource não puder ser inicializado
  });
