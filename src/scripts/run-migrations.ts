import { AppDataSource } from '../data/data-source';
import { Logger } from '../utils/logger';

const logger = new Logger();

async function runMigrations() {
  try {
    logger.info('Iniciando conexão com o banco de dados...');
    await AppDataSource.initialize();
    
    logger.info('Executando migrações...');
    await AppDataSource.runMigrations();
    
    logger.info('Migrações executadas com sucesso!');
    process.exit(0);
  } catch (error) {
    logger.error('Erro ao executar migrações:', error);
    process.exit(1);
  }
}

runMigrations(); 