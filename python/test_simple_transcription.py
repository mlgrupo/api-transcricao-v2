#!/usr/bin/env python3
"""
Teste simples de transcrição sem diarização
"""

import asyncio
import sys
import os
from pathlib import Path

# Adicionar o diretório atual ao path
sys.path.append(str(Path(__file__).parent))

from robust_transcription_adapter import get_adapter
import structlog

logger = structlog.get_logger()

async def test_simple_transcription():
    """Testa transcrição simples sem diarização"""
    
    # Verificar se foi fornecido um arquivo de áudio
    if len(sys.argv) < 2:
        print("Uso: python test_simple_transcription.py <arquivo_audio>")
        print("Exemplo: python test_simple_transcription.py audio.mp3")
        return
    
    audio_path = sys.argv[1]
    
    # Verificar se o arquivo existe
    if not os.path.exists(audio_path):
        print(f"❌ Arquivo não encontrado: {audio_path}")
        return
    
    try:
        logger.info("🧪 Iniciando teste de transcrição simples")
        
        # Obter adaptador
        adapter = get_adapter()
        
        # Verificar status
        status = adapter.get_system_status()
        logger.info("📊 Status do sistema:", status=status)
        
        # Transcrever
        logger.info(f"🎯 Transcrevendo: {audio_path}")
        start_time = asyncio.get_event_loop().time()
        
        transcription = await adapter.transcribe_audio(audio_path)
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        logger.info("✅ Transcrição concluída!")
        logger.info(f"⏱️ Tempo total: {duration:.2f} segundos")
        logger.info(f"📝 Tamanho da transcrição: {len(transcription)} caracteres")
        
        print("\n" + "="*60)
        print("📝 TRANSCRIÇÃO COM TIMESTAMPS:")
        print("="*60)
        print(transcription)
        print("="*60)
        
        # Salvar em arquivo
        output_file = f"{Path(audio_path).stem}_transcription.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(transcription)
        
        logger.info(f"💾 Transcrição salva em: {output_file}")
        
    except Exception as e:
        logger.error(f"❌ Erro no teste: {e}")
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple_transcription()) 