import { MigrationInterface, QueryRunner } from "typeorm";

export class AddTimestampsToSystemConfig1700000003000 implements MigrationInterface {
    name = 'AddTimestampsToSystemConfig1700000003000'

    public async up(queryRunner: QueryRunner): Promise<void> {
        // Verificar se as colunas já existem
        const hasCreatedAt = await queryRunner.hasColumn("system_config", "created_at");
        const hasUpdatedAt = await queryRunner.hasColumn("system_config", "updated_at");
        
        if (!hasCreatedAt) {
            await queryRunner.query(`
                ALTER TABLE "system_config" 
                ADD COLUMN "created_at" TIMESTAMP NOT NULL DEFAULT NOW()
            `);
        }
        
        if (!hasUpdatedAt) {
            await queryRunner.query(`
                ALTER TABLE "system_config" 
                ADD COLUMN "updated_at" TIMESTAMP NOT NULL DEFAULT NOW()
            `);
        }
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "system_config" DROP COLUMN "updated_at"`);
        await queryRunner.query(`ALTER TABLE "system_config" DROP COLUMN "created_at"`);
    }
} 