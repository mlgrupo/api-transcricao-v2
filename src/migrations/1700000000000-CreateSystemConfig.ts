import { MigrationInterface, QueryRunner, Table } from "typeorm";

export class CreateSystemConfig1700000000000 implements MigrationInterface {
    name = 'CreateSystemConfig1700000000000'

    public async up(queryRunner: QueryRunner): Promise<void> {
        const tableExists = await queryRunner.hasTable("system_config");
        if (!tableExists) {
            await queryRunner.createTable(
                new Table({
                    name: "system_config",
                    columns: [
                        {
                            name: "id",
                            type: "serial",
                            isPrimary: true,
                        },
                        {
                            name: "key",
                            type: "varchar",
                            length: "100",
                            isNullable: false,
                        },
                        {
                            name: "value",
                            type: "jsonb",
                            isNullable: false,
                            default: "'[]'",
                        },
                    ],
                }),
                true
            );
        }
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        const tableExists = await queryRunner.hasTable("system_config");
        if (tableExists) {
            await queryRunner.dropTable("system_config");
        }
    }
} 