import { MigrationInterface, QueryRunner, TableColumn } from "typeorm";

export class AddProgressEtapaToVideos1700000001000 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    const table = await queryRunner.getTable('transcricao_v2.videos_mapeados');
    if (table && !table.findColumnByName('progress')) {
      await queryRunner.addColumn('transcricao_v2.videos_mapeados', new TableColumn({
        name: 'progress',
        type: 'integer',
        isNullable: true,
        default: 0,
      }));
    }
    if (table && !table.findColumnByName('etapa_atual')) {
      await queryRunner.addColumn('transcricao_v2.videos_mapeados', new TableColumn({
        name: 'etapa_atual',
        type: 'varchar',
        isNullable: true,
      }));
    }
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    const table = await queryRunner.getTable('transcricao_v2.videos_mapeados');
    if (table && table.findColumnByName('progress')) {
      await queryRunner.dropColumn('transcricao_v2.videos_mapeados', 'progress');
    }
    if (table && table.findColumnByName('etapa_atual')) {
      await queryRunner.dropColumn('transcricao_v2.videos_mapeados', 'etapa_atual');
    }
  }
} 