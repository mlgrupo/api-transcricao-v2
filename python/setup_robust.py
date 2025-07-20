#!/usr/bin/env python3
"""
Setup Robusto para Arquitetura de Diarização
Configurado para servidor Linux com 8 vCPUs e 32GB RAM
Suporte a 2 vídeos de 2h simultâneos
"""

import os
import sys
import subprocess
import platform
import psutil
import json
from pathlib import Path
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RobustSetup:
    def __init__(self):
        self.system_info = self._get_system_info()
        self.requirements_file = "requirements-robust.txt"
        self.test_results = {}
        
    def _get_system_info(self):
        """Coleta informações do sistema"""
        return {
            'platform': platform.system(),
            'architecture': platform.machine(),
            'python_version': sys.version,
            'cpu_count': psutil.cpu_count(),
            'memory_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'available_memory_gb': round(psutil.virtual_memory().available / (1024**3), 2)
        }
    
    def check_system_compatibility(self):
        """Verifica compatibilidade do sistema"""
        logger.info("=== VERIFICAÇÃO DE COMPATIBILIDADE ===")
        
        # Verificar sistema operacional
        if self.system_info['platform'] not in ['Linux', 'Windows']:
            logger.error(f"Sistema operacional não suportado: {self.system_info['platform']}")
            return False
        
        # Verificar memória
        if self.system_info['memory_gb'] < 16:
            logger.error(f"Memória insuficiente: {self.system_info['memory_gb']}GB (mínimo: 16GB)")
            return False
        
        # Verificar CPUs
        if self.system_info['cpu_count'] < 4:
            logger.warning(f"Poucos CPUs: {self.system_info['cpu_count']} (recomendado: 8+)")
        
        logger.info(f"✅ Sistema compatível:")
        logger.info(f"   - OS: {self.system_info['platform']}")
        logger.info(f"   - CPUs: {self.system_info['cpu_count']}")
        logger.info(f"   - RAM: {self.system_info['memory_gb']}GB")
        logger.info(f"   - Python: {sys.version.split()[0]}")
        
        return True
    
    def install_dependencies(self):
        """Instala dependências com otimizações"""
        logger.info("=== INSTALAÇÃO DE DEPENDÊNCIAS ===")
        
        try:
            # Atualizar pip
            logger.info("Atualizando pip...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                         check=True, capture_output=True)
            
            # Instalar torch com otimização para CPU
            logger.info("Instalando PyTorch otimizado para CPU...")
            if self.system_info['platform'] == 'Linux':
                subprocess.run([
                    sys.executable, "-m", "pip", "install", 
                    "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cpu"
                ], check=True, capture_output=True)
            else:
                subprocess.run([
                    sys.executable, "-m", "pip", "install", "torch", "torchaudio"
                ], check=True, capture_output=True)
            
            # Instalar outras dependências
            logger.info("Instalando dependências principais...")
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", self.requirements_file
            ], check=True, capture_output=True)
            
            logger.info("✅ Dependências instaladas com sucesso!")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro na instalação: {e}")
            return False
    
    def verify_installations(self):
        """Verifica se as instalações foram bem-sucedidas"""
        logger.info("=== VERIFICAÇÃO DE INSTALAÇÕES ===")
        
        packages_to_check = [
            'torch', 'torchaudio', 'whisper', 'pyannote.audio', 
            'librosa', 'psutil', 'numpy', 'scipy'
        ]
        
        for package in packages_to_check:
            try:
                __import__(package)
                logger.info(f"✅ {package}: OK")
                self.test_results[package] = "OK"
            except ImportError as e:
                logger.error(f"❌ {package}: FALHOU - {e}")
                self.test_results[package] = f"FALHOU: {e}"
                return False
        
        return True
    
    def test_whisper_setup(self):
        """Testa configuração do Whisper"""
        logger.info("=== TESTE WHISPER ===")
        
        try:
            import whisper
            model = whisper.load_model("base")  # Carrega modelo menor para teste
            logger.info("✅ Whisper carregado com sucesso")
            self.test_results['whisper_test'] = "OK"
            return True
        except Exception as e:
            logger.error(f"❌ Erro no Whisper: {e}")
            self.test_results['whisper_test'] = f"FALHOU: {e}"
            return False
    
    def test_pyannote_setup(self):
        """Testa configuração do PyAnnote"""
        logger.info("=== TESTE PYANNOTE ===")
        
        try:
            from pyannote.audio import Pipeline
            logger.info("✅ PyAnnote importado com sucesso")
            self.test_results['pyannote_test'] = "OK"
            return True
        except Exception as e:
            logger.error(f"❌ Erro no PyAnnote: {e}")
            self.test_results['pyannote_test'] = f"FALHOU: {e}"
            return False
    
    def test_memory_usage(self):
        """Testa uso de memória"""
        logger.info("=== TESTE DE MEMÓRIA ===")
        
        try:
            import psutil
            import torch
            
            # Simular carregamento de modelo
            logger.info("Simulando carregamento de modelo...")
            
            # Criar tensor grande para teste
            test_tensor = torch.randn(1000, 1000)
            memory_used = psutil.virtual_memory().used / (1024**3)
            
            logger.info(f"Memória em uso: {memory_used:.2f}GB")
            
            if memory_used < 28:  # Limite de segurança
                logger.info("✅ Uso de memória dentro dos limites")
                self.test_results['memory_test'] = "OK"
                return True
            else:
                logger.warning(f"⚠️ Uso de memória alto: {memory_used:.2f}GB")
                self.test_results['memory_test'] = "ALTO"
                return True  # Não é erro, apenas aviso
                
        except Exception as e:
            logger.error(f"❌ Erro no teste de memória: {e}")
            self.test_results['memory_test'] = f"FALHOU: {e}"
            return False
    
    def create_config_file(self):
        """Cria arquivo de configuração otimizada"""
        logger.info("=== CRIANDO CONFIGURAÇÃO ===")
        
        config = {
            "system": {
                "max_concurrent_jobs": 2,
                "max_memory_gb": 28,
                "chunk_duration": 30,
                "chunk_overlap": 5,
                "whisper_model": "large-v3",
                "max_speakers": 8
            },
            "performance": {
                "batch_size": 4,
                "timeout_per_chunk": 600,  # 10 minutos
                "retry_attempts": 3,
                "cleanup_interval": 30
            },
            "monitoring": {
                "log_interval": 30,
                "memory_alert_threshold": 25,
                "enable_metrics": True
            }
        }
        
        config_path = Path("robust_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"✅ Configuração salva em: {config_path}")
        return True
    
    def run_full_setup(self):
        """Executa setup completo"""
        logger.info("🚀 INICIANDO SETUP ROBUSTO")
        logger.info("=" * 50)
        
        # Verificar compatibilidade
        if not self.check_system_compatibility():
            logger.error("❌ Sistema incompatível. Setup abortado.")
            return False
        
        # Instalar dependências
        if not self.install_dependencies():
            logger.error("❌ Falha na instalação. Setup abortado.")
            return False
        
        # Verificar instalações
        if not self.verify_installations():
            logger.error("❌ Falha na verificação. Setup abortado.")
            return False
        
        # Testes específicos
        if not self.test_whisper_setup():
            logger.error("❌ Falha no teste do Whisper.")
            return False
        
        if not self.test_pyannote_setup():
            logger.error("❌ Falha no teste do PyAnnote.")
            return False
        
        if not self.test_memory_usage():
            logger.error("❌ Falha no teste de memória.")
            return False
        
        # Criar configuração
        self.create_config_file()
        
        # Relatório final
        logger.info("=" * 50)
        logger.info("🎉 SETUP CONCLUÍDO COM SUCESSO!")
        logger.info("=" * 50)
        logger.info("RESULTADOS DOS TESTES:")
        for test, result in self.test_results.items():
            logger.info(f"  {test}: {result}")
        
        logger.info("\n📋 PRÓXIMOS PASSOS:")
        logger.info("1. Execute: python test_robust_architecture.py")
        logger.info("2. Configure tokens do HuggingFace se necessário")
        logger.info("3. Teste com arquivo de áudio real")
        
        return True

def main():
    """Função principal"""
    setup = RobustSetup()
    success = setup.run_full_setup()
    
    if success:
        print("\n✅ Setup robusto concluído com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Setup falhou. Verifique os logs acima.")
        sys.exit(1)

if __name__ == "__main__":
    main() 