
export class CredentialService {
  constructor(private db: any) {}

  async findById(id: number): Promise<any | null> {
    return await this.db.findOne({ where: { id } });
  }

  async findByUserId(userId: string): Promise<any | null> {
    return await this.db.findOne({ where: { user_id: userId } });
  }

  async create(credential: any): Promise<any> {
    return await this.db.save(credential);
  }

  async update(id: number, credential: Partial<any>): Promise<void> {
    await this.db.update(id, credential);
  }

  async delete(id: number): Promise<void> {
    await this.db.delete(id);
  }
}