import { MigrationInterface, QueryRunner } from "typeorm";

export class AddGoogleDocsUrlToVideos1700000002000 implements MigrationInterface {
    name = 'AddGoogleDocsUrlToVideos1700000002000'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`
            ALTER TABLE "transcricao_v2"."videos_mapeados" 
            ADD COLUMN "google_docs_url" VARCHAR NULL
        `);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`
            ALTER TABLE "transcricao_v2"."videos_mapeados" 
            DROP COLUMN "google_docs_url"
        `);
    }
} 