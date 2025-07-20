@echo off
echo Configurando ambiente local para testes...

REM Criar arquivo .env se nao existir
if not exist .env (
    echo Criando arquivo .env...
    (
        echo # Configuracoes do Banco de Dados
        echo DATABASE_URL=postgresql://postgres:password@localhost:5432/transcricao_ia
        echo.
        echo # Configuracoes do Google
        echo GOOGLE_CLIENT_ID=seu_google_client_id
        echo GOOGLE_CLIENT_SECRET=seu_google_client_secret
        echo GOOGLE_REDIRECT_URI=http://localhost:3001/auth/google/callback
        echo.
        echo # Configuracoes do HuggingFace ^(para arquitetura robusta^)
        echo HUGGINGFACE_TOKEN=seu_huggingface_token
        echo.
        echo # Configuracoes do OpenAI ^(opcional, para melhor performance^)
        echo OPENAI_API_KEY=sua_openai_api_key
        echo.
        echo # Configuracoes do Servidor
        echo PORT=3001
        echo NODE_ENV=development
        echo.
        echo # Configuracoes CORS
        echo CORS_ORIGIN=http://localhost:3000,http://localhost:3001
        echo.
        echo # Configuracoes de Pastas do Google Drive
        echo ROOT_FOLDER_NAME=Meet Recordings
        echo FOLDER_NAME_GRAVACAO=Gravacao
        echo FOLDER_NAME_TRANSCRICAO=Transcricao
        echo.
        echo # Configuracoes de Webhook
        echo WEBHOOK_URL=http://localhost:3000/webhook
        echo.
        echo # Configuracoes de Recursos ^(arquitetura robusta^)
        echo MAX_RAM_GB=30
        echo MAX_CPU_PERCENT=80
        echo MAX_CONCURRENT_JOBS=2
        echo.
        echo # Configuracoes de Log
        echo LOG_LEVEL=info
        echo.
        echo # JWT Secret
        echo JWT_SECRET=seu_jwt_secret_super_secreto_para_desenvolvimento
        echo.
        echo # API Key para autenticacao
        echo API_KEY=sua_api_key_para_desenvolvimento
    ) > .env
    echo Arquivo .env criado!
) else (
    echo Arquivo .env ja existe!
)

REM Verificar arquivos da arquitetura robusta
if exist python\requirements-robust.txt (
    echo Arquivos da arquitetura robusta encontrados!
    echo Para instalar dependencias Python, execute:
    echo cd python ^&^& pip install -r requirements-robust.txt
) else (
    echo Arquivos da arquitetura robusta nao encontrados!
    echo Execute primeiro: cd python ^&^& python init_robust_system.py
)

echo.
echo PROXIMOS PASSOS:
echo 1. Configure as variaveis no arquivo .env
echo 2. Configure um banco PostgreSQL local
echo 3. Execute: npm run build
echo 4. Execute: npm run migrate
echo 5. Execute: npm start
echo.
echo Para configurar arquitetura robusta:
echo    cd python ^&^& python init_robust_system.py
echo.
echo Ambiente local configurado!
pause 