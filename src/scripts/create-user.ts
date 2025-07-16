import { AppDataSource } from "../data/data-source";
import { Collaborator } from "../domain/models/Collaborators";
import bcrypt from "bcryptjs";

async function createUserIfNotExists({
  userId,
  name,
  email,
  password,
  isAdmin = false,
  picture
}: {
  userId: string;
  name: string;
  email: string;
  password: string;
  isAdmin?: boolean;
  picture?: string;
}) {
  const repo = AppDataSource.getRepository(Collaborator);
  const existing = await repo.findOneBy({ email });
  if (existing) {
    console.log(`Usuário já existe: ${email}`);
    return existing;
  }
  const hashedPassword = await bcrypt.hash(password, 10);
  const user = repo.create({
    userId,
    name,
    email,
    password: hashedPassword,
    isAdmin,
    ...(picture ? { picture } : {})
  });
  await repo.save(user);
  console.log(`Usuário criado: ${email}`);
  return user;
}

// Exemplo de uso:
(async () => {
  await AppDataSource.initialize();
  await createUserIfNotExists({
    userId: 'admin',
    name: 'Administrador',
    email: 'admin@admin.com',
    password: 'admin123',
    isAdmin: true
  });
  process.exit(0);
})(); 