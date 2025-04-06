import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn} from "typeorm";

@Entity({ name: "videos_mapeados", schema: "transcricao_v2" })
export class Video {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ name: "video_id", type: "varchar" })
  videoId!: string;

  @Column({ name: "usuario_id", nullable: true, type: "varchar" })
  usuarioId?: string;

  @Column({ name: "video_name", type: "varchar" })
  videoName!: string;

  @Column({ name: "user_email", type: "varchar" })
  userEmail!: string;

  @Column({ name: "pasta_id", nullable: true, type: "varchar" })
  pastaId?: string;

  @Column({ name: "created_time", nullable: true, type: "timestamp" })
  createdTime?: Date;

  @Column({ name: "mime_type", nullable: true, type: "varchar" })
  mimeType?: string;

  @Column({ default: false, type: "boolean" })
  transcrito!: boolean;

  @Column({ default: false, type: "boolean" })
  enfileirado!: boolean;

  @Column({ nullable: true, type: "varchar" })
  status?: string;

  @Column({ name: "error_message", nullable: true, type: "text" })
  errorMessage?: string;

  @CreateDateColumn({ name: "dt_criacao" })
  dtCriacao!: Date;

  @UpdateDateColumn({ name: "dt_atualizacao", nullable: true })
  dtAtualizacao?: Date;
}