import { MigrationInterface, QueryRunner } from "typeorm";

export class AddUserIdToSystemConfig1700000004000 implements MigrationInterface {
    public async up(queryRunner: QueryRunner): Promise<void> {
        const tableExists = await queryRunner.hasTable("system_config");
        if (tableExists) {
            await queryRunner.query(`ALTER TABLE system_config ADD COLUMN "userId" varchar(100) NULL;`);
        }
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE system_config DROP COLUMN "userId";`);
    }
} 