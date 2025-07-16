# Transcrição IA - Deploy Plug and Play

## Pré-requisitos
- Node.js 18+
- Python 3.9+
- PostgreSQL (Railway ou local)

## 1. Clone o projeto
```bash
git clone https://github.com/seu-usuario/seu-repo.git
cd seu-repo
```

## 2. Instale as dependências Node.js
```bash
npm install
```

## 3. Instale as dependências Python
```bash
bash install-python-deps.sh
```

## 4. Configure o .env
Copie o exemplo:
```bash
cp .env.example .env
```
Preencha as variáveis do banco, Google, HuggingFace, etc.

## 5. Rode o backend
```bash
npm start
```
- As migrações serão aplicadas automaticamente.
- Um usuário admin será criado automaticamente (veja seed em `src/data/seed-manager.ts`).

## 6. Deploy no Railway
- Crie um novo projeto Node.js e um banco PostgreSQL.
- Defina as variáveis do `.env` no painel do Railway.
- O Railway executa `npm install` e `npm run build` automaticamente.
- Rode o script de dependências Python no painel (ou adicione ao build se usar Docker).

## 7. Acesse o sistema
- O admin padrão estará disponível (veja email/senha no seed ou crie o seu).

## 8. Controle de versão
- Use GitHub normalmente para versionar, criar branches, PRs, etc.

---

**Dúvidas? Só perguntar!** 