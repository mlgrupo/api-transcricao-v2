/**
 * Define os tipos de subpastas principais diretamente sob a pasta raiz.
 * Estas são as pastas de segundo nível na hierarquia.
 */
export type MainSubFolderType = 'Gravação' | 'Transcrição';

/**
 * Define os nomes das pastas específicas (terceiro nível),
 * que são baseadas nos valores do objeto MAPPED_FOLDERS no ManagerFileAndFolder.ts.
 * Ex: 'Treinamento', 'Onboarding', 'Encontro em Grupo', 'Acompanhamento'.
 * 
 * Nota: Se os valores em MAPPED_FOLDERS mudarem, este tipo precisará ser
 * atualizado manualmente para manter a consistência, a menos que uma
 * forma mais dinâmica de derivação de tipo seja implementada.
 */
export type SpecificFolderType = string;

/**
 * Representa a estrutura de nomes para uma hierarquia de pastas de dois níveis.
 * Exemplo: Meet Recordings / Transcrição
 */
export interface ITwoLevelNamedHierarchy {
  /**
   * Nome da pasta raiz.
   * Ex: "Meet Recordings" (definido como ROOT_FOLDER no ManagerFileAndFolder.ts)
   */
  rootFolder: string;
  /**
   * Nome da subpasta principal (segundo nível).
   */
  mainSubFolder: MainSubFolderType;
}

/**
 * Representa a estrutura de nomes para uma hierarquia de pastas de três níveis.
 * Exemplo: Meet Recordings / Transcrição / Treinamento
 */
export interface IThreeLevelNamedHierarchy extends ITwoLevelNamedHierarchy {
  /**
   * Nome da pasta específica (terceiro nível), determinada pelo prefixo do arquivo.
   */
  specificFolder: SpecificFolderType;
}

/**
 * Um tipo união para representar qualquer uma das hierarquias de nomes de pastas
 * válidas no sistema, podendo ser uma estrutura de 2 ou 3 níveis.
 */
export type NamedFolderHierarchy = ITwoLevelNamedHierarchy | IThreeLevelNamedHierarchy; 
