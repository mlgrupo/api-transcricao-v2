import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn, ManyToOne, JoinColumn } from "typeorm";
import { Collaborator } from "./Collaborators";

@Entity({ name: "credentials", schema: "transcricao_v2" })
export class Credential {
  @PrimaryGeneratedColumn()
  id!: number;

  @Column({ name: "user_id", type: "varchar" })
  userId!: string;

  @Column({ type: "varchar" })
  name!: string;

  @Column({ unique: true, type: "varchar" })
  email!: string;

  @Column({ nullable: true, type: "varchar" })
  picture?: string;

  @Column({ name: "access_token", type: "text" })
  accessToken!: string;

  @Column({ name: "refresh_token", nullable: true, type: "text" })
  refreshToken?: string;

  @Column({ nullable: true, type: "text" })
  scope?: string;

  @Column({ name: "token_type", nullable: true, type: "varchar" })
  tokenType?: string;

  @Column({ name: "expiry_date", nullable: true, type: "bigint" })
  expiryDate?: number;

  @Column({ default: true, type: "boolean" })
  ativo!: boolean;

  @CreateDateColumn({ name: "created_at" })
  createdAt!: Date;

  @UpdateDateColumn({ name: "updated_at" })
  updatedAt!: Date;

  @ManyToOne(() => Collaborator)
  @JoinColumn({ name: "user_id", referencedColumnName: "userId" })
  collaborator!: Collaborator;
}