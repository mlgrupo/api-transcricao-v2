export interface IDriveService {
  getFileById: (drive: any, fileId: string) => Promise<any>;
  createFolder: (drive: any, folderName: string, parentFolderId?: string) => Promise<string>;
  moveFile: (drive: any, fileId: string, addParents: string, removeParents: string) => Promise<any>;
  uploadFile: (drive: any, folderId: string, filename: string, mimeType: string, bodyContent: string) => Promise<any>;
}

