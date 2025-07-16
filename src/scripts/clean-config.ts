import { AppDataSource } from '../data/data-source';
import { SystemConfig } from '../domain/models/SystemConfig';
import { Logger } from '../utils/logger';

const logger = new Logger();

async function cleanInvalidConfigs() {
  try {
    // Inicializar DataSource
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
      logger.info('✅ DataSource inicializado');
    }

    // Buscar configuração atual
    const configRepo = AppDataSource.getRepository(SystemConfig);
    const rootFolderConfig = await configRepo.findOne({ where: { key: 'root_folder' } });

    if (rootFolderConfig) {
      logger.info('Configuração atual encontrada:', rootFolderConfig.value);

      // Limpar configurações inválidas (IDs que não são válidos)
      let currentValue = rootFolderConfig.value;
      if (typeof currentValue === 'string') {
        try {
          currentValue = JSON.parse(currentValue);
        } catch (error) {
          logger.warn('Erro ao fazer parse da configuração:', error);
          currentValue = [];
        }
      }

      if (Array.isArray(currentValue)) {
        // Filtrar apenas IDs válidos (mínimo 10 caracteres, apenas letras, números, hífen e underscore)
        const validFolders = currentValue.filter((folder: string) => {
          // Se for um link válido do Google Drive
          if (folder.includes('drive.google.com') && folder.includes('folders/')) {
            return true;
          }
          // Se for um nome de pasta (não é ID)
          if (!/^[a-zA-Z0-9_-]{10,}$/.test(folder)) {
            return true;
          }
          // Se for um ID válido
          return /^[a-zA-Z0-9_-]{10,}$/.test(folder);
        });

        logger.info(`Pastas válidas encontradas: ${validFolders.length}`, validFolders);

        // Atualizar configuração apenas com pastas válidas
        if (validFolders.length !== currentValue.length) {
          rootFolderConfig.value = validFolders;
          await configRepo.save(rootFolderConfig);
          logger.info('✅ Configuração limpa e atualizada');
        } else {
          logger.info('✅ Configuração já está limpa');
        }
      }
    } else {
      logger.info('Nenhuma configuração de pasta encontrada');
    }

  } catch (error: any) {
    logger.error('❌ Erro ao limpar configurações:', error);
  } finally {
    if (AppDataSource.isInitialized) {
      await AppDataSource.destroy();
      logger.info('✅ Conexão com banco fechada');
    }
  }
}

// Executar se chamado diretamente
if (require.main === module) {
  cleanInvalidConfigs()
    .then(() => {
      logger.info('✅ Script de limpeza concluído');
      process.exit(0);
    })
    .catch((error) => {
      logger.error('❌ Erro no script de limpeza:', error);
      process.exit(1);
    });
}

export { cleanInvalidConfigs }; 