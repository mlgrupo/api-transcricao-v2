import { MigrationInterface, QueryRunner } from "typeorm";

export class CreateSystemConfig1700000000000 implements MigrationInterface {
    name = 'CreateSystemConfig1700000000000'

    public async up(queryRunner: QueryRunner): Promise<void> {
        // Verificar se a tabela já existe
        const tableExists = await queryRunner.hasTable("system_config");
        
        if (!tableExists) {
            await queryRunner.query(`
                CREATE TABLE "system_config" (
                    "id" SERIAL NOT NULL,
                    "key" character varying(100) NOT NULL,
                    "value" jsonb NOT NULL DEFAULT '[]',
                    CONSTRAINT "PK_system_config" PRIMARY KEY ("id")
                )
            `);
        }
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`DROP TABLE "system_config"`);
    }
} 