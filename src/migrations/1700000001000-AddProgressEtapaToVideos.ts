import { MigrationInterface, QueryRunner } from "typeorm";

export class AddProgressEtapaToVideos1700000001000 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "transcricao_v2"."videos_mapeados" ADD COLUMN "progress" integer DEFAULT 0;`
    );
    await queryRunner.query(
      `ALTER TABLE "transcricao_v2"."videos_mapeados" ADD COLUMN "etapa_atual" varchar NULL;`
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "transcricao_v2"."videos_mapeados" DROP COLUMN "progress";`
    );
    await queryRunner.query(
      `ALTER TABLE "transcricao_v2"."videos_mapeados" DROP COLUMN "etapa_atual";`
    );
  }
} 