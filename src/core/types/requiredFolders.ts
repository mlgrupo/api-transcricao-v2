export type RequiredFolders = {
  rootFolder: string;
  folderRecording: string;
  folderTranscription: string;
  // aqui aonde será as pastas conforme o nome do video ex: // Treinamento, Onboarding
  nomenclatureFolders: {
    [key: string]: string;
  };
}
