import { Entity, Column, PrimaryColumn, CreateDateColumn, UpdateDateColumn } from "typeorm";

@Entity({ name: "collaborators", schema: "transcricao_v2" })
export class Collaborator {
  @PrimaryColumn({ name: "user_id", type: "varchar" })
  userId!: string;

  @Column({ type: "varchar" })
  name!: string;

  @Column({ unique: true, type: "varchar" })
  email!: string;

  @Column({ nullable: true, type: "varchar" })
  picture?: string;

  @Column({ nullable: true, type: "varchar" })
  folderRootName?: string;

  @Column({ nullable: true, type: "varchar" })
  password?: string;

  @Column({ default: false, type: "boolean" })
  isAdmin!: boolean;

  @CreateDateColumn({ name: "created_at" })
  createdAt!: Date;

  @UpdateDateColumn({ name: "updated_at" })
  updatedAt!: Date;
}
