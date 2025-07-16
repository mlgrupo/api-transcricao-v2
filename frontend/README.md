# Frontend - Sistema de Transcrição IA

Frontend em Next.js para o sistema de transcrição automática de áudio/vídeo.

## Funcionalidades

- **Login com Google OAuth**: Autenticação integrada com Google
- **Dashboard**: Estatísticas em tempo real das transcrições
- **Lista de Vídeos**: Visualização de todas as transcrições
- **Status da API**: Monitoramento do status do backend
- **Interface Responsiva**: Design simples e funcional

## Tecnologias

- Next.js 15
- React 19
- TypeScript
- CSS Modules (sem Tailwind)

## Como Executar

1. **Instalar dependências:**
   ```bash
   npm install
   ```

2. **Executar em desenvolvimento:**
   ```bash
   npm run dev
   ```

3. **Acessar:**
   - Frontend: http://localhost:3000
   - Backend: http://localhost:3001 (deve estar rodando)

## Variáveis de Ambiente

Crie um arquivo `.env.local` na raiz do frontend:

```env
NEXT_PUBLIC_API_URL=http://localhost:3001
```

## Estrutura do Projeto

```
src/
├── app/
│   ├── components/
│   │   ├── LoginButton.tsx
│   │   ├── Dashboard.tsx
│   │   ├── VideoList.tsx
│   │   └── ApiStatus.tsx
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
```

## Scripts Disponíveis

- `npm run dev`: Executa em modo desenvolvimento
- `npm run build`: Gera build de produção
- `npm run start`: Executa build de produção
- `npm run lint`: Executa linter

## Integração com Backend

O frontend se comunica com o backend através das seguintes rotas:

- `GET /auth/status`: Verifica status da autenticação
- `GET /auth/google`: Inicia fluxo OAuth
- `POST /auth/logout`: Faz logout
- `GET /videos`: Lista vídeos/transcrições
- `GET /health`: Verifica status da API

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
