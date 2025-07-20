# Script para configurar ambiente local
Write-Host "Configurando ambiente local para testes..." -ForegroundColor Green

# Criar arquivo .env se não existir
$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Criando arquivo .env..." -ForegroundColor Yellow
    
    $envContent = @"
# Configuracoes do Banco de Dados
DATABASE_URL=postgresql://postgres:password@localhost:5432/transcricao_ia

# Configuracoes do Google
GOOGLE_CLIENT_ID=seu_google_client_id
GOOGLE_CLIENT_SECRET=seu_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3001/auth/google/callback

# Configuracoes do HuggingFace (para arquitetura robusta)
HUGGINGFACE_TOKEN=seu_huggingface_token

# Configuracoes do OpenAI (opcional, para melhor performance)
OPENAI_API_KEY=sua_openai_api_key

# Configuracoes do Servidor
PORT=3001
NODE_ENV=development

# Configuracoes CORS
CORS_ORIGIN=http://localhost:3000,http://localhost:3001

# Configuracoes de Pastas do Google Drive
ROOT_FOLDER_NAME=Meet Recordings
FOLDER_NAME_GRAVACAO=Gravacao
FOLDER_NAME_TRANSCRICAO=Transcricao

# Configuracoes de Webhook
WEBHOOK_URL=http://localhost:3000/webhook

# Configuracoes de Recursos (arquitetura robusta)
MAX_RAM_GB=30
MAX_CPU_PERCENT=80
MAX_CONCURRENT_JOBS=2

# Configuracoes de Log
LOG_LEVEL=info

# JWT Secret
JWT_SECRET=seu_jwt_secret_super_secreto_para_desenvolvimento

# API Key para autenticacao
API_KEY=sua_api_key_para_desenvolvimento
"@
    
    $envContent | Out-File -FilePath $envFile -Encoding UTF8
    Write-Host "Arquivo .env criado!" -ForegroundColor Green
} else {
    Write-Host "Arquivo .env ja existe!" -ForegroundColor Green
}

# Verificar se estamos no diretório python
if (Test-Path "python") {
    Write-Host "Navegando para diretorio python..." -ForegroundColor Yellow
    Set-Location "python"
    
    # Verificar se os arquivos da arquitetura robusta existem
    $robustFiles = @(
        "requirements-robust.txt",
        "resource_manager.py",
        "audio_chunker.py",
        "whisper_processor.py",
        "speaker_diarizer.py",
        "transcription_merger.py",
        "diarization_orchestrator.py",
        "robust_transcription_adapter.py"
    )
    
    $missingFiles = @()
    foreach ($file in $robustFiles) {
        if (-not (Test-Path $file)) {
            $missingFiles += $file
        }
    }
    
    if ($missingFiles.Count -gt 0) {
        Write-Host "Arquivos da arquitetura robusta nao encontrados:" -ForegroundColor Yellow
        foreach ($file in $missingFiles) {
            Write-Host "   - $file" -ForegroundColor Red
        }
        Write-Host "Execute primeiro: python init_robust_system.py" -ForegroundColor Cyan
    } else {
        Write-Host "Todos os arquivos da arquitetura robusta encontrados!" -ForegroundColor Green
        
        # Perguntar se quer instalar dependências Python
        $installPython = Read-Host "Deseja instalar dependencias Python da arquitetura robusta? (s/n)"
        if ($installPython -eq "s" -or $installPython -eq "S") {
            Write-Host "Instalando dependencias Python..." -ForegroundColor Yellow
            pip install -r requirements-robust.txt
        }
    }
    
    # Voltar para diretório raiz
    Set-Location ".."
} else {
    Write-Host "Diretorio python nao encontrado!" -ForegroundColor Red
}

Write-Host ""
Write-Host "PROXIMOS PASSOS:" -ForegroundColor Cyan
Write-Host "1. Configure as variaveis no arquivo .env" -ForegroundColor White
Write-Host "2. Configure um banco PostgreSQL local" -ForegroundColor White
Write-Host "3. Execute: npm run build" -ForegroundColor White
Write-Host "4. Execute: npm run migrate" -ForegroundColor White
Write-Host "5. Execute: npm start" -ForegroundColor White
Write-Host ""
Write-Host "Para configurar arquitetura robusta:" -ForegroundColor Cyan
Write-Host "   cd python && python init_robust_system.py" -ForegroundColor White
Write-Host ""
Write-Host "Ambiente local configurado!" -ForegroundColor Green 