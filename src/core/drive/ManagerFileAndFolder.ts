import { drive_v3 } from 'googleapis'
import type { DriveService } from './drive-service'
import { Readable } from 'stream'
import type { transcriptionTreeFolders } from './interfaces/ITranscriptionTreeFolders'
import type { WebhookService } from '../../infrastructure/webhook/webhook-sender'

// Mapeia o prefixo (primeira "palavra") do nome → pasta aonde vai a transcrição e a gravação
const MAPPED_FOLDERS = {
  treinamento: 'Treinamento',
  onboarding: 'Onboarding',
  encontro: 'Encontro em Grupo',
  acompanhamento: 'Acompanhamento',
  revisao: 'Revisão',
  entrevista: 'Entrevista',
  consultoria: 'Consultoria',

} as const

// Pasta raiz fixa
const ROOT_FOLDER = 'Meet Recordings'

type FileType = keyof typeof MAPPED_FOLDERS
type SubFolder = 'Gravação' | 'Transcrição'

export class ManagerFileAndFolder {
  constructor(private driveService: DriveService, private webhookService: WebhookService) {}

  public async organize(drive: drive_v3.Drive, fileName: string, transcriptionContent: string | Buffer, mimeType: string, videoId: string): Promise<boolean> {
    const lower = fileName.toLowerCase()

    // 1 - detecta prefixo
    const prefixKey = (Object.keys(MAPPED_FOLDERS) as FileType[]).find(key =>
      lower.startsWith(key)
    )

    // 2- decide qual subpasta ele vai ir com base no mimetype
    const subFolderType: SubFolder =
      mimeType.startsWith('video/') || mimeType.startsWith('audio/')
        ? 'Gravação'
        : mimeType.startsWith('text/') || mimeType.includes('json')
        ? 'Transcrição'
        : (() => { throw new Error(`MimeType não suportado: '${mimeType}'`) })()

    // 3 -  fluxo sem prefixo -  se o usuario colocar o nome do video que nao contenha no mappedFolders acima ele entra neste fluxo e salva na pasta de gravação e na pasta de transcrição
    if (!prefixKey) {
      return await this.handleNoPrefix(drive, fileName, transcriptionContent, subFolderType, mimeType, videoId, "Gravação")
    }

    // 4) fluxo com prefixo: 3 níveis ROOT/Tipo/Prefixo
    const baseFolder = MAPPED_FOLDERS[prefixKey]
    const tree: transcriptionTreeFolders = {
      rootFolder: ROOT_FOLDER,
      subFolder: subFolderType,
      mappedSubFolder: baseFolder,
    }
    const ids = await this.verifyIfImportantFoldersExistsIfNotCreate(tree, drive)
    const targetFolderId = ids.mappedSubFolder as string
    const targetPath = `${ROOT_FOLDER}/${subFolderType}/${baseFolder}`

    if (subFolderType === 'Transcrição') {
      // cria DOCX
      const docName = `${fileName}-transcricao.docx`
      const mediaBody = typeof transcriptionContent === 'string'
        ? Readable.from([transcriptionContent])
        : transcriptionContent

      await drive.files.create({
        requestBody: {
          name: docName,
          parents: [targetFolderId],
          mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        },
        media: {
          mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          body: mediaBody,
        },
      })
      console.log(`📄 Transcrição gravada: '${docName}' em '${targetPath}'`)

      // move vídeo para Gravação correspondente
      const recTree: transcriptionTreeFolders = {
        rootFolder: ROOT_FOLDER,
        subFolder: 'Gravação',
        mappedSubFolder: baseFolder,
      }
      const recIds = await this.verifyIfImportantFoldersExistsIfNotCreate(recTree, drive)
      await this.moveFileIfNeeded(drive, videoId, recIds.mappedSubFolder as string, `${ROOT_FOLDER}/Gravação/${baseFolder}`)
      return true
    }

    // subFolderType === 'Gravação'
    await this.moveFileIfNeeded(drive, videoId, targetFolderId, targetPath)
    return false
  }

  private async handleNoPrefix(drive: drive_v3.Drive, fileName: string, transcriptionContent: string | Buffer, subFolderType: SubFolder, mimeType: string, videoId: string, subfolderTypeVideo: string): Promise<boolean> {
    // garante hierarquia ROOT/Tipo
    const parentId = await this.ensureTwoLevelFolderExists(ROOT_FOLDER, subFolderType, drive)
    const path = `${ROOT_FOLDER}/${subFolderType}`

    // vou crair o arquivo direto na pasta de destino
    if (subFolderType === 'Transcrição') {
      const docName = `${fileName}`
      const mediaBody = typeof transcriptionContent === 'string'
        ? Readable.from([transcriptionContent])
        : transcriptionContent

      await drive.files.create({
        requestBody: { name: docName, parents: [parentId], mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
        media: { mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', body: mediaBody },
      })

      console.log(`📄 Transcrição (sem prefixo) gravada: '${docName}' em '${path}'`)
      const recordingParentId = await this.ensureTwoLevelFolderExists(ROOT_FOLDER, 'Gravação', drive);
      const recordingPath = `${ROOT_FOLDER}/Gravação`;
      await this.moveFileIfNeeded(drive, videoId, recordingParentId, recordingPath);

      this.webhookService.sendNotification('https://whk.supercaso.com.br/webhook/error-organize', {
        videoId: videoId,
        message: `Transcrição (sem prefixo) gravada: '${docName}' em '${path}'`,
        status: 'attention'
      });
      
      return true
    }

    if (subFolderType === 'Gravação') {
      await this.moveFileIfNeeded(drive, videoId, parentId, path)
      return false;
    }
    
    if (subFolderType === 'Transcrição') {
        return true;
    } else {
        return false;
    }
  }

  private async ensureTwoLevelFolderExists(
    rootName: string,
    subName: string,
    drive: drive_v3.Drive
  ): Promise<string> {
    // cria/obtém pasta raiz
    const rootResult = await this.driveService.checkFolderHasCreated(rootName, drive)
    const rootId = rootResult?.folderId ?? await this.driveService.createFolder(drive, rootName)

    // cria/obtém subpasta
    const subResult = await this.driveService.checkFolderHasCreated(subName, drive, rootId)
    return subResult?.folderId ?? await this.driveService.createFolder(drive, subName, rootId)
  }

  private async verifyIfImportantFoldersExistsIfNotCreate(tree: transcriptionTreeFolders, drive: drive_v3.Drive): Promise<transcriptionTreeFolders> {
    try {
      // 1 -  raiz - Meet Recordings
      const rootRes = await this.driveService.checkFolderHasCreated(tree.rootFolder, drive)
      tree.rootFolder = rootRes?.folderId ?? await this.driveService.createFolder(drive, tree.rootFolder)
      // 2 - sub - Gravação
      const subRes = await this.driveService.checkFolderHasCreated(tree.subFolder, drive, tree.rootFolder)
      tree.subFolder = subRes?.folderId ?? await this.driveService.createFolder(drive, tree.subFolder, tree.rootFolder)
      // 3 - mapeada - Treinamento, Onboarding, Encontro em Grupo, Acompanhamento
      const mapRes = await this.driveService.checkFolderHasCreated(tree.mappedSubFolder, drive, tree.subFolder)
      tree.mappedSubFolder = mapRes?.folderId ?? await this.driveService.createFolder(drive, tree.mappedSubFolder, tree.subFolder)
      return tree
    } catch (error) {
      throw new Error(`Erro ao criar/verificar hierarquia de pastas: ${error}`)
    }
  }

  private async moveFileIfNeeded(drive: drive_v3.Drive, fileId: string, newParentId: string, readablePath: string): Promise<void> {
    const { data } = await drive.files.get({ fileId, fields: 'parents' })
    const oldParent = data.parents?.[0];
    if (oldParent && oldParent !== newParentId) {
      await drive.files.update({ fileId, addParents: newParentId, removeParents: oldParent })
      console.log(`✅ Vídeo movido para: '${readablePath}'`)
    }
  }
}
