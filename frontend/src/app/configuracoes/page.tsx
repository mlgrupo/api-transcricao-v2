"use client";
import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from "next/navigation";
import { fetchWithAuth } from '../utils/fetchWithAuth';
import { FiFolder, FiMove, FiLink, FiSave, FiArrowLeft, FiPlus, FiTrash2, FiZap } from 'react-icons/fi';

interface Webhook {
  id: string;
  url: string;
  name: string;
  description: string;
  events: string[];
  active: boolean;
}

export default function ConfiguracoesPage() {
  const [activeTab, setActiveTab] = useState('folders');
  const [folders, setFolders] = useState<string[]>([""]);
  const [transcriptionFolder, setTranscriptionFolder] = useState('');
  const [moveVideoAfterTranscription, setMoveVideoAfterTranscription] = useState(false);
  const [videoDestinationFolder, setVideoDestinationFolder] = useState('');
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9898';

  // Proteção local para evitar múltiplos fetchs por montagem
  const fetchedOnce = useRef(false);
  // Buscar configuração atual
  useEffect(() => {
    if (fetchedOnce.current) return;
    fetchedOnce.current = true;
    const abortController = new AbortController();
    const fetchConfig = async () => {
      try {
        setLoading(true);
        const response = await fetchWithAuth(`${API_BASE_URL}/api/config/root-folder`, { signal: abortController.signal });
        if (response.ok) {
          const data = await response.json();
          if (Array.isArray(data.folders)) {
            setFolders(data.folders.length > 0 ? data.folders : [""]);
          } else if (typeof data.folders === 'string') {
            setFolders([data.folders]);
          } else {
            setFolders([""]);
          }
        } else {
          setError('Erro ao carregar configuração');
        }
      } catch (error) {
        if (abortController.signal.aborted) return; // Ignora se foi cancelado
        setError('Erro de conexão');
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
    // Cleanup para cancelar fetch se desmontar
    return () => {
      abortController.abort();
    };
  }, []);

  // Buscar webhooks do backend ao montar
  useEffect(() => {
    const fetchWebhooks = async () => {
      try {
        const response = await fetchWithAuth(`${API_BASE_URL}/api/config/webhooks`);
        if (response.ok) {
          const data = await response.json();
          if (Array.isArray(data.webhooks)) {
            setWebhooks(data.webhooks);
          } else {
            setWebhooks([]);
          }
        }
      } catch (error) {
        // Ignora erro de conexão
      }
    };
    fetchWebhooks();
  }, []);

  // Buscar configuração de transcrição ao montar
  useEffect(() => {
    const fetchTranscriptionConfig = async () => {
      try {
        const response = await fetchWithAuth(`${API_BASE_URL}/api/config/transcription`);
        if (response.ok) {
          const data = await response.json();
          if (typeof data === 'object' && data !== null) {
            setTranscriptionFolder(data.transcriptionFolder || '');
            setMoveVideoAfterTranscription(Boolean(data.moveVideoAfterTranscription));
            setVideoDestinationFolder(data.videoDestinationFolder || '');
          }
        }
      } catch (error) {
        // Ignora erro de conexão
      }
    };
    fetchTranscriptionConfig();
  }, [API_BASE_URL]);

  // Salvar webhooks no backend sempre que alterar
  const saveWebhooks = async (webhooksToSave: Webhook[]) => {
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/config/webhooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ webhooks: webhooksToSave })
      });
    } catch (error) {
      // Ignora erro de conexão
    }
  };

  // Função de validação igual ao backend
  function isValidDriveFolder(input: string): boolean {
    const linkRegex = /^https:\/\/drive\.google\.com\/drive\/folders\/[a-zA-Z0-9_-]{10,}/;
    const idRegex = /^[a-zA-Z0-9_-]{10,}$/;
    const nameRegex = /\S+/;
    return linkRegex.test(input) || idRegex.test(input) || nameRegex.test(input);
  }

  // Salvar configuração de pastas
  const handleSaveFolders = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSuccess(false);
    setError(null);
    const foldersToSend = folders.map(f => f.trim()).filter(f => f.length > 0);
    if (foldersToSend.length === 0) {
      setError('Informe pelo menos uma pasta.');
      setSaving(false);
      return;
    }
    // Validação local antes de enviar
    const invalids = foldersToSend.filter(f => !isValidDriveFolder(f));
    if (invalids.length > 0) {
      setError(`Os seguintes itens são inválidos: ${invalids.join(', ')}`);
      setSaving(false);
      return;
    }
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/config/root-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: foldersToSend })
      });
      if (response.ok) {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Erro ao salvar configuração');
      }
    } catch (error) {
      setError('Erro de conexão');
    } finally {
      setSaving(false);
    }
  };

  // Salvar configuração de transcrição
  const handleSaveTranscriptionConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSuccess(false);
    setError(null);
    
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/config/transcription`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcriptionFolder,
          moveVideoAfterTranscription,
          videoDestinationFolder: moveVideoAfterTranscription ? videoDestinationFolder : null
        })
      });
      if (response.ok) {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Erro ao salvar configuração');
      }
    } catch (error) {
      setError('Erro de conexão');
    } finally {
      setSaving(false);
    }
  };

  const handleFolderChange = (idx: number, value: string) => {
    setFolders(folders => folders.map((f, i) => (i === idx ? value : f)));
  };

  const handleAddFolder = () => {
    setFolders(folders => [...folders, ""]);
  };

  const handleRemoveFolder = (idx: number) => {
    setFolders(folders => folders.length === 1 ? [""] : folders.filter((_, i) => i !== idx));
  };

  const handleAddWebhook = () => {
    const newWebhook: Webhook = {
      id: Date.now().toString(),
      url: '',
      name: '',
      description: '',
      events: ['transcription_completed'],
      active: true
    };
    const updated = [...webhooks, newWebhook];
    setWebhooks(updated);
    saveWebhooks(updated);
  };

  const handleRemoveWebhook = (id: string) => {
    const updated = webhooks.filter(w => w.id !== id);
    setWebhooks(updated);
    saveWebhooks(updated);
  };

  const handleWebhookChange = (id: string, field: keyof Webhook, value: any) => {
    const updated = webhooks.map(w => w.id === id ? { ...w, [field]: value } : w);
    setWebhooks(updated);
    saveWebhooks(updated);
  };

  const handleTestWebhook = async (webhook: Webhook) => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/webhooks/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(webhook)
      });
      if (response.ok) {
        alert('Webhook testado com sucesso!');
      } else {
        alert('Erro ao testar webhook');
      }
    } catch (error) {
      alert('Erro ao testar webhook');
    }
  };

  // Novo estado para feedback de webhooks
  const [webhookSaveSuccess, setWebhookSaveSuccess] = useState(false);
  const [webhookSaveError, setWebhookSaveError] = useState<string | null>(null);

  // Nova função para salvar webhooks manualmente
  const handleSaveWebhooks = async () => {
    setWebhookSaveSuccess(false);
    setWebhookSaveError(null);
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/config/webhooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ webhooks })
      });
      setWebhookSaveSuccess(true);
      setTimeout(() => setWebhookSaveSuccess(false), 3000);
    } catch (error) {
      setWebhookSaveError('Erro ao salvar webhooks');
      setTimeout(() => setWebhookSaveError(null), 3000);
    }
  };

  // Lista de eventos possíveis
  const ALL_EVENTS = [
    { id: 'transcription_completed', label: 'Transcrição concluída' },
    { id: 'transcription_failed', label: 'Transcrição falhou' },
    { id: 'video_processing', label: 'Processamento iniciado' },
  ];

  const handleWebhookEventChange = (id: string, eventId: string, checked: boolean) => {
    setWebhooks(webhooks => webhooks.map(w =>
      w.id === id
        ? { ...w, events: checked ? [...new Set([...w.events, eventId])] : w.events.filter(e => e !== eventId) }
        : w
    ));
  };

  return (
    <div style={{ 
      maxWidth: 900, 
      margin: '40px auto', 
      padding: 24,
      background: '#111111',
      color: '#FFE1A6'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
        <h2 style={{ 
          fontSize: '2.2rem', 
          fontWeight: 700, 
          margin: 0, 
          color: '#FFE1A6' 
        }}>
          Configurações
        </h2>
        <button 
          onClick={() => router.push('/dashboard')} 
          className="button secondary"
          style={{ display: 'flex', alignItems: 'center', gap: 8 }}
        >
          <FiArrowLeft size={16} />
          Voltar ao Dashboard
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
        {[
          { id: 'folders', label: 'Pastas', icon: FiFolder },
          { id: 'transcription', label: 'Transcrição', icon: FiMove },
          { id: 'webhooks', label: 'Webhooks', icon: FiLink }
        ].map(tab => {
          const IconComponent = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`button ${activeTab === tab.id ? '' : 'secondary'}`}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 8,
                padding: '0.75rem 1.5rem'
              }}
            >
              <IconComponent size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <div className="loading" style={{ margin: '0 auto 1rem' }}></div>
          <p style={{ color: '#FFE1A6' }}>Carregando configurações...</p>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div style={{ 
          color: '#FFE1A6', 
          marginBottom: 24, 
          padding: '1rem', 
          background: 'rgba(76, 0, 13, 0.2)', 
          borderRadius: '8px', 
          border: '1px solid rgba(76, 0, 13, 0.4)' 
        }}>
          ❌ {error}
        </div>
      )}

      {/* Success state */}
      {success && (
        <div style={{ 
          color: '#FFE1A6', 
          marginBottom: 24, 
          padding: '1rem', 
          background: 'rgba(76, 0, 13, 0.2)', 
          borderRadius: '8px', 
          border: '1px solid rgba(76, 0, 13, 0.4)' 
        }}>
          ✅ Configuração salva com sucesso!
        </div>
      )}

      {activeTab === 'folders' && (
        <div className="card">
          <h3 style={{ marginBottom: 24, color: '#FFE1A6', fontSize: '1.5rem' }}>
            Configuração de Pastas
          </h3>
          <form onSubmit={handleSaveFolders}>
            <div style={{ marginBottom: 24 }}>
              <label style={{ fontWeight: 500, marginBottom: 8, display: 'block', color: '#FFE1A6' }}>
                Pastas para monitorar:
              </label>
              {folders.map((folder, idx) => (
                <div key={idx} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <input
                    type="text"
                    className="input"
                    value={folder}
                    onChange={e => handleFolderChange(idx, e.target.value)}
                    placeholder="Nome, ID ou link completo da pasta do Google Drive"
                    style={{ flex: 1 }}
                  />
                  {folders.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveFolder(idx)}
                      className="button danger"
                      style={{ padding: '0.5rem', display: 'flex', alignItems: 'center' }}
                    >
                      <FiTrash2 size={16} />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={handleAddFolder}
                className="button secondary"
                style={{ display: 'flex', alignItems: 'center', gap: 8 }}
              >
                <FiPlus size={16} />
                Adicionar Pasta
              </button>
            </div>
            <button type="submit" className="button success" disabled={saving} style={{ width: 180 }}>
              <FiSave size={16} />
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
          </form>
        </div>
      )}

      {activeTab === 'transcription' && (
        <div className="card">
          <h3 style={{ marginBottom: 24, color: '#FFE1A6', fontSize: '1.5rem' }}>
            Configurações de Transcrição
          </h3>
          <form onSubmit={handleSaveTranscriptionConfig}>
            <div style={{ marginBottom: 24 }}>
              <label style={{ fontWeight: 500, marginBottom: 8, display: 'block', color: '#FFE1A6' }}>
                Pasta de destino das transcrições:
              </label>
              <input
                type="text"
                className="input"
                value={transcriptionFolder}
                onChange={e => setTranscriptionFolder(e.target.value)}
                placeholder="Nome, ID ou link completo da pasta onde salvar transcrições"
                style={{ marginBottom: 8 }}
              />
              <p style={{ fontSize: '0.875rem', color: 'rgba(255, 225, 166, 0.7)', margin: 0 }}>
                Deixe vazio para usar a pasta padrão "Transcrição". Aceita nome, ID ou link completo do Google Drive.
              </p>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={{ fontWeight: 500, marginBottom: 8, display: 'block', color: '#FFE1A6' }}>
                Movimentação de vídeos após transcrição:
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <input
                  type="checkbox"
                  id="moveVideo"
                  checked={moveVideoAfterTranscription}
                  onChange={e => setMoveVideoAfterTranscription(e.target.checked)}
                  style={{ width: 18, height: 18 }}
                />
                <label htmlFor="moveVideo" style={{ cursor: 'pointer', color: '#FFE1A6' }}>
                  Mover vídeo após concluir transcrição
                </label>
              </div>
              {moveVideoAfterTranscription && (
                <div style={{ marginLeft: 30 }}>
                  <input
                    type="text"
                    className="input"
                    value={videoDestinationFolder}
                    onChange={e => setVideoDestinationFolder(e.target.value)}
                    placeholder="Nome, ID ou link completo da pasta de destino"
                    style={{ marginBottom: 8 }}
                  />
                  <p style={{ fontSize: '0.875rem', color: 'rgba(255, 225, 166, 0.7)', margin: 0 }}>
                    Pasta onde o vídeo será movido após a transcrição. Aceita nome, ID ou link completo do Google Drive.
                  </p>
                </div>
              )}
            </div>

            {error && (
              <div style={{ color: '#FFE1A6', marginBottom: 16, padding: '0.75rem', background: 'rgba(76, 0, 13, 0.2)', borderRadius: '8px', border: '1px solid rgba(76, 0, 13, 0.4)' }}>
                ❌ {error}
              </div>
            )}
            {success && (
              <div style={{ color: '#FFE1A6', marginBottom: 16, padding: '0.75rem', background: 'rgba(76, 0, 13, 0.2)', borderRadius: '8px', border: '1px solid rgba(76, 0, 13, 0.4)' }}>
                ✅ Configuração salva com sucesso!
              </div>
            )}
            <button type="submit" className="button success" disabled={saving} style={{ width: 180 }}>
              <FiSave size={16} />
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
          </form>
        </div>
      )}

      {activeTab === 'webhooks' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h3 style={{ margin: 0, color: '#FFE1A6', fontSize: '1.5rem' }}>
              Gerenciamento de Webhooks
            </h3>
            <button
              onClick={handleAddWebhook}
              className="button info"
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <FiPlus size={16} />
              Adicionar Webhook
            </button>
          </div>

          {/* Feedback visual de salvar webhooks */}
          {webhookSaveSuccess && (
            <div style={{ color: '#FFE1A6', marginBottom: 16, padding: '0.75rem', background: 'rgba(76, 0, 13, 0.2)', borderRadius: '8px', border: '1px solid rgba(76, 0, 13, 0.4)' }}>
              ✅ Webhooks salvos com sucesso!
            </div>
          )}
          {webhookSaveError && (
            <div style={{ color: '#FFE1A6', marginBottom: 16, padding: '0.75rem', background: 'rgba(76, 0, 13, 0.2)', borderRadius: '8px', border: '1px solid rgba(76, 0, 13, 0.4)' }}>
              ❌ {webhookSaveError}
            </div>
          )}

          {webhooks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'rgba(255, 225, 166, 0.7)' }}>
              <FiLink size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
              <p>Nenhum webhook configurado</p>
              <button
                onClick={handleAddWebhook}
                className="button info"
                style={{ marginTop: '1rem' }}
              >
                <FiPlus size={16} />
                Adicionar primeiro webhook
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {webhooks.map((webhook) => (
                <div key={webhook.id} className="card" style={{ 
                  background: 'rgba(17, 17, 17, 0.8)', 
                  border: '1px solid rgba(76, 0, 13, 0.4)',
                  padding: '1.5rem'
                }}>
                  <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <input
                        type="text"
                        className="input"
                        value={webhook.name}
                        onChange={e => handleWebhookChange(webhook.id, 'name', e.target.value)}
                        placeholder="Nome do webhook"
                        style={{ marginBottom: 8 }}
                      />
                      <input
                        type="text"
                        className="input"
                        value={webhook.url}
                        onChange={e => handleWebhookChange(webhook.id, 'url', e.target.value)}
                        placeholder="URL do webhook"
                        style={{ marginBottom: 8 }}
                      />
                      <textarea
                        className="input"
                        value={webhook.description}
                        onChange={e => handleWebhookChange(webhook.id, 'description', e.target.value)}
                        placeholder="Descrição do webhook"
                        rows={3}
                        style={{ marginBottom: 8, resize: 'vertical' }}
                      />
                      <div style={{ marginBottom: 8 }}>
                        <span style={{ fontWeight: 500, color: '#FFE1A6', marginRight: 8 }}>Eventos:</span>
                        {ALL_EVENTS.map(ev => (
                          <label key={ev.id} style={{ marginRight: 16, fontSize: '0.95em', color: '#FFE1A6' }}>
                            <input
                              type="checkbox"
                              checked={webhook.events.includes(ev.id)}
                              onChange={e => handleWebhookEventChange(webhook.id, ev.id, e.target.checked)}
                              style={{ marginRight: 4 }}
                            />
                            {ev.label}
                          </label>
                        ))}
                      </div>
                    </div>
                    <button
                      onClick={() => handleTestWebhook(webhook)}
                      className="button info"
                      style={{ padding: '0.5rem', display: 'flex', alignItems: 'center' }}
                      title="Testar webhook"
                    >
                      <FiZap size={16} />
                    </button>
                    <button
                      onClick={() => handleRemoveWebhook(webhook.id)}
                      className="button danger"
                      style={{ padding: '0.5rem', display: 'flex', alignItems: 'center' }}
                      title="Remover webhook"
                    >
                      <FiTrash2 size={16} />
                    </button>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input
                        type="checkbox"
                        checked={webhook.active}
                        onChange={e => handleWebhookChange(webhook.id, 'active', e.target.checked)}
                        style={{ width: 16, height: 16 }}
                      />
                      <span style={{ fontSize: '0.875rem', color: '#FFE1A6' }}>Ativo</span>
                    </div>
                    <div style={{ fontSize: '0.875rem', color: 'rgba(255, 225, 166, 0.7)' }}>
                      Eventos selecionados: {webhook.events.map(ev => ALL_EVENTS.find(e => e.id === ev)?.label || ev).join(', ')}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: 24, padding: '1rem', background: 'rgba(76, 0, 13, 0.1)', borderRadius: '8px', border: '1px solid rgba(76, 0, 13, 0.4)' }}>
            <h4 style={{ margin: '0 0 8px 0', color: '#FFE1A6' }}>📋 Informações sobre Webhooks:</h4>
            <ul style={{ margin: 0, paddingLeft: 20, color: 'rgba(255, 225, 166, 0.8)', fontSize: '0.875rem' }}>
              <li><strong>transcription_completed:</strong> Enviado quando uma transcrição é concluída</li>
              <li><strong>transcription_failed:</strong> Enviado quando uma transcrição falha</li>
              <li><strong>video_processing:</strong> Enviado quando um vídeo inicia processamento</li>
              <li>O payload inclui: videoId, videoName, status, transcription (se concluída), error (se falhou)</li>
            </ul>
          </div>
          {/* Botão de salvar webhooks */}
          <div style={{ marginTop: 24, textAlign: 'right' }}>
            <button className="button success" onClick={handleSaveWebhooks} style={{ minWidth: 180 }}>
              <FiSave size={16} /> Salvar Webhooks
            </button>
          </div>
        </div>
      )}
    </div>
  );
} 