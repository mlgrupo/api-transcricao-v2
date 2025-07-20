# 🔄 Guia Completo - Como Atualizar o Repositório

## 📋 **Situações e Soluções:**

### **1. Atualização Simples (Sem alterações locais):**
```bash
# Verificar status
git status

# Atualizar
git pull origin main
```

### **2. Com Alterações Locais que Quer Manter:**
```bash
# Salvar alterações locais
git add .
git commit -m "Minhas alterações locais"

# Atualizar
git pull origin main
```

### **3. Descartar Alterações Locais:**
```bash
# Descartar tudo
git reset --hard HEAD
git clean -fd

# Atualizar
git pull origin main
```

### **4. Script Automático (Recomendado):**
```bash
# Dar permissão
chmod +x update_repo.sh

# Executar
./update_repo.sh
```

## 🚀 **Passo a Passo Detalhado:**

### **Passo 1: Verificar Status**
```bash
git status
```

**Possíveis resultados:**
- `working tree clean` → Pode atualizar diretamente
- `modified: arquivo.txt` → Há alterações locais

### **Passo 2: Decidir o que fazer**

#### **Se não há alterações locais:**
```bash
git pull origin main
```

#### **Se há alterações locais e quer manter:**
```bash
git add .
git commit -m "Alterações locais antes da atualização"
git pull origin main
```

#### **Se há alterações locais e quer descartar:**
```bash
git reset --hard HEAD
git clean -fd
git pull origin main
```

### **Passo 3: Verificar se funcionou**
```bash
git log --oneline -5
```

## ⚠️ **Cenários Especiais:**

### **Se der erro de conflito:**
```bash
# Ver conflitos
git status

# Resolver conflitos manualmente nos arquivos
# Depois:
git add .
git commit -m "Resolvendo conflitos"
```

### **Se der erro de branch:**
```bash
# Verificar branch atual
git branch

# Mudar para main se necessário
git checkout main

# Atualizar
git pull origin main
```

### **Se der erro de remote:**
```bash
# Verificar remotes
git remote -v

# Adicionar remote se necessário
git remote add origin https://github.com/seu-usuario/seu-repo.git

# Atualizar
git pull origin main
```

## 🔧 **Comandos Úteis:**

### **Verificar informações:**
```bash
git status          # Status atual
git branch          # Branch atual
git remote -v       # Remotes configurados
git log --oneline   # Histórico
```

### **Limpar e resetar:**
```bash
git reset --hard HEAD    # Descartar alterações
git clean -fd            # Remover arquivos não rastreados
git stash                # Salvar temporariamente
git stash pop            # Restaurar temporários
```

### **Forçar atualização:**
```bash
git fetch origin
git reset --hard origin/main
```

## 📊 **Exemplos Práticos:**

### **Exemplo 1: Atualização Limpa**
```bash
$ git status
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean

$ git pull origin main
Already up to date.
```

### **Exemplo 2: Com Alterações Locais**
```bash
$ git status
On branch main
Your branch is behind 'origin/main' by 2 commits, and can be fast-forwarded.
  (use "git pull" to update your local branch)
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
        modified:   python/robust_transcribe.py

$ git add .
$ git commit -m "Minhas alterações"
$ git pull origin main
```

### **Exemplo 3: Usando o Script**
```bash
$ ./update_repo.sh
🔄 Verificando status do repositório...
📊 Status atual:
M  python/robust_transcribe.py

⚠️  ATENÇÃO: Há alterações locais não commitadas!

Opções:
1. Salvar alterações locais e atualizar
2. Descartar alterações locais e atualizar
3. Cancelar

Escolha uma opção (1-3): 1
💾 Salvando alterações locais...
✅ Alterações salvas!
📥 Fazendo pull das mudanças...
✅ Repositório atualizado com sucesso!
```

## 🎯 **Recomendações:**

### **Para Desenvolvimento:**
1. **Sempre** verifique o status antes de atualizar
2. **Faça commit** das suas alterações importantes
3. **Use o script** para atualizações seguras
4. **Teste** após atualizar

### **Para Produção:**
1. **Backup** antes de atualizar
2. **Teste** em ambiente de desenvolvimento
3. **Use tags** para versões estáveis
4. **Monitore** após atualizar

## 🎉 **Resultado Esperado:**

Após uma atualização bem-sucedida, você deve ver:
- ✅ Repositório atualizado
- ✅ Últimas mudanças aplicadas
- ✅ Sistema funcionando normalmente
- ✅ Correções e otimizações ativas

**Use o script `update_repo.sh` para uma atualização segura e automática!** 🔄 