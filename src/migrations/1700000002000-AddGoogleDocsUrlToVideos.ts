import { MigrationInterface, QueryRunner, TableColumn } from "typeorm";

export class AddGoogleDocsUrlToVideos1700000002000 implements MigrationInterface {
    name = 'AddGoogleDocsUrlToVideos1700000002000'

    public async up(queryRunner: QueryRunner): Promise<void> {
        const table = await queryRunner.getTable('transcricao_v2.videos_mapeados');
        if (table && !table.findColumnByName('google_docs_url')) {
            await queryRunner.addColumn('transcricao_v2.videos_mapeados', new TableColumn({
                name: 'google_docs_url',
                type: 'varchar',
                isNullable: true,
            }));
        }
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        const table = await queryRunner.getTable('transcricao_v2.videos_mapeados');
        if (table && table.findColumnByName('google_docs_url')) {
            await queryRunner.dropColumn('transcricao_v2.videos_mapeados', 'google_docs_url');
        }
    }
} 