import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn } from "typeorm";

@Entity({ name: "system_config", schema: "transcricao_v2" })
export class SystemConfig {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ type: "varchar", length: 100, unique: false })
  key!: string;

  @Column({ type: "jsonb", default: "[]" })
  value!: any;

  @Column({ type: "varchar", length: 100, nullable: true })
  userId?: string | null;

  @CreateDateColumn({ name: "created_at" })
  createdAt!: Date;

  @UpdateDateColumn({ name: "updated_at" })
  updatedAt!: Date;
} 