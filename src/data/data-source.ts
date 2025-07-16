import { DataSource } from "typeorm";
import { Collaborator } from "../domain/models/Collaborators";
import { Video } from "../domain/models/Video";
import { Credential } from "../domain/models/Credentials";
import { ApplicationLog } from "../domain/models/ApplicationLog"; // Importar a entidade ApplicationLog
import { SystemConfig } from "../domain/models/SystemConfig";
import { initializeDevSeed } from "./seed-manager";
import dotenv from 'dotenv';

const envFile = `.env.${process.env.NODE_ENV ?? 'development'}`;

dotenv.config({ path: envFile });

const databaseUrl = process.env.DATABASE_URL;

let dataSourceOptions: any;

if (databaseUrl) {
  // Railway ou qualquer URL única
  dataSourceOptions = {
    type: "postgres",
    url: databaseUrl,
    synchronize: false,
    logging: process.env.NODE_ENV === "development",
    entities: [
      Video,
      Collaborator,
      Credential,
      ApplicationLog,
      SystemConfig,
    ],
    migrations: [process.env.NODE_ENV === "production" ? "dist/migrations/**/*.js" : "src/migrations/**/*.ts"],
    subscribers: [process.env.NODE_ENV === "production" ? "dist/subscribers/**/*.js" : "src/subscribers/**/*.ts"],
    extra: { charset: "utf8" }
  };
} else {
  // Configuração tradicional
  const requiredEnvVars = {
    DB_HOST: process.env.DB_HOST,
    DB_PORT: parseInt(process.env.DB_PORT ?? "5432"),
    DB_USERNAME: process.env.DB_USERNAME,
    DB_PASSWORD: String(process.env.DB_PASSWORD),
    DB_DATABASE: process.env.DB_DATABASE
  };

  if (!requiredEnvVars.DB_PASSWORD) {
    console.error("❌ Erro: DB_PASSWORD não está definida nas variáveis de ambiente");
    process.exit(1);
  }

  dataSourceOptions = {
    type: "postgres",
    host: requiredEnvVars.DB_HOST,
    port: requiredEnvVars.DB_PORT,
    username: requiredEnvVars.DB_USERNAME,
    password: requiredEnvVars.DB_PASSWORD,
    database: requiredEnvVars.DB_DATABASE,
    synchronize: false,
    logging: process.env.NODE_ENV === "development",
    entities: [
      Video,
      Collaborator,
      Credential,
      ApplicationLog,
      SystemConfig,
    ],
    migrations: ["src/migrations/**/*.ts"],
    subscribers: ["src/subscribers/**/*.ts"],
    extra: { charset: "utf8" }
  };
}

export const AppDataSource = new DataSource(dataSourceOptions);

AppDataSource.initialize()
  .then(async () => {
    console.log('✅ DataSource inicializado com sucesso.');
    // Executar migrações pendentes
    try {
      await AppDataSource.runMigrations();
      console.log('✅ Migrações executadas com sucesso.');
      // Rodar seed de admin
      const { initializeDevSeed } = require('./seed-manager');
      await initializeDevSeed();
      console.log('✅ Seed de admin executado com sucesso.');
    } catch (error) {
      console.log('ℹ️ Nenhuma migração pendente ou erro ao executar migrações/seed:', error);
    }
  })
  .catch((error) => {
    console.error('❌ Erro ao inicializar o DataSource:', error);
    process.exit(1); // Finaliza o processo se o DataSource não puder ser inicializado
  });
