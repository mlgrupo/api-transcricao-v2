import { MigrationInterface, QueryRunner } from "typeorm";

export class AddProgressEtapaToVideos1700000001000 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    // Adiciona a coluna 'progress' apenas se não existir
    await queryRunner.query(`
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema = 'transcricao_v2'
            AND table_name = 'videos_mapeados'
            AND column_name = 'progress'
        ) THEN
          ALTER TABLE "transcricao_v2"."videos_mapeados" ADD COLUMN "progress" integer DEFAULT 0;
        END IF;
      END
      $$;
    `);
    // Adiciona a coluna 'etapa_atual' apenas se não existir
    await queryRunner.query(`
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema = 'transcricao_v2'
            AND table_name = 'videos_mapeados'
            AND column_name = 'etapa_atual'
        ) THEN
          ALTER TABLE "transcricao_v2"."videos_mapeados" ADD COLUMN "etapa_atual" varchar NULL;
        END IF;
      END
      $$;
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "transcricao_v2"."videos_mapeados" DROP COLUMN IF EXISTS "progress";`
    );
    await queryRunner.query(
      `ALTER TABLE "transcricao_v2"."videos_mapeados" DROP COLUMN IF EXISTS "etapa_atual";`
    );
  }
} 