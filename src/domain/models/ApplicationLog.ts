import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn } from "typeorm";

@Entity({ name: "application_logs", schema: "transcricao_v2" })
export class ApplicationLog {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: "varchar", length: 50 })
  level!: string;

  @Column({ type: "text" })
  message!: string;

  @Column({ type: "jsonb", nullable: true })
  metadata?: Record<string, any>;

  @CreateDateColumn({ name: "timestamp" })
  timestamp!: Date;
}
