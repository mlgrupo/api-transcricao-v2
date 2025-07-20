#!/bin/bash

# 🔄 Script para Atualizar Repositório
# Atualiza o repositório de forma segura

echo "🔄 Verificando status do repositório..."

# Verificar se é um repositório git
if [ ! -d ".git" ]; then
    echo "❌ Erro: Esta pasta não é um repositório git!"
    exit 1
fi

# Verificar status atual
echo "📊 Status atual:"
git status --porcelain

# Verificar se há alterações não commitadas
if [ -n "$(git status --porcelain)" ]; then
    echo ""
    echo "⚠️  ATENÇÃO: Há alterações locais não commitadas!"
    echo ""
    echo "Opções:"
    echo "1. Salvar alterações locais e atualizar"
    echo "2. Descartar alterações locais e atualizar"
    echo "3. Cancelar"
    echo ""
    read -p "Escolha uma opção (1-3): " choice
    
    case $choice in
        1)
            echo "💾 Salvando alterações locais..."
            git add .
            git commit -m "Alterações locais antes da atualização"
            echo "✅ Alterações salvas!"
            ;;
        2)
            echo "🗑️  Descartando alterações locais..."
            git reset --hard HEAD
            git clean -fd
            echo "✅ Alterações descartadas!"
            ;;
        3)
            echo "❌ Operação cancelada!"
            exit 0
            ;;
        *)
            echo "❌ Opção inválida!"
            exit 1
            ;;
    esac
fi

# Fazer pull das mudanças
echo "📥 Fazendo pull das mudanças..."
git pull origin main

# Verificar se houve conflitos
if [ $? -eq 0 ]; then
    echo "✅ Repositório atualizado com sucesso!"
    echo ""
    echo "📋 Últimas mudanças:"
    git log --oneline -5
else
    echo "❌ Erro ao atualizar repositório!"
    echo "Verifique se há conflitos de merge."
fi

echo ""
echo "🎉 Atualização concluída!" 