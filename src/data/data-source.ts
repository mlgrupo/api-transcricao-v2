import { DataSource } from "typeorm";
import dotenv from "dotenv";
import { Collaborator } from "../domain/models/Collaborators";
import { Video } from "../domain/models/Video";
import { Credential } from "../domain/models/Credentials";
import { ApplicationLog } from "../domain/models/ApplicationLog"; // Importar a entidade ApplicationLog

dotenv.config();
export const AppDataSource = new DataSource({
  type: "postgres",
  host: process.env.DB_HOST || "localhost",
  port: parseInt(process.env.DB_PORT || "5432"),
  username: process.env.DB_USERNAME || "root",
  password: process.env.DB_PASSWORD || "root",
  database: process.env.DB_NAME || "db-ia",
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
  .then(() => {
    console.log('✅ DataSource inicializado com sucesso.');
  })
  .catch((error) => {
    console.error('❌ Erro ao inicializar o DataSource:', error);
    process.exit(1); // Finaliza o processo se o DataSource não puder ser inicializado
  });
