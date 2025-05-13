import { Collaborator } from "../domain/models/Collaborators";
import { Credential } from "../domain/models/Credentials";

export interface DevSeedData {
  collaborator: Collaborator;
  credential: Credential;
}

export function getDevSeedData(): DevSeedData {
  const userId = "103829492068001740031";
  const email = "developers@reconectaoficial.com.br";

  // Cria um colaborador de desenvolvimento
  const devCollaborator = new Collaborator();
  devCollaborator.userId = userId;
  devCollaborator.name = "developers Central";
  devCollaborator.email = email;
  devCollaborator.picture = "https://lh3.googleusercontent.com/a/ACg8ocK2viWXwMx0QPNwBWTZnqzQkKtbRgInCle7Ah3DB7UJyv-VTQ=s96-c";
  devCollaborator.folderRootName = "Meet Recordings";

  // Cria uma credencial para o colaborador
  const devCredential = new Credential();
  devCredential.userId = userId;
  devCredential.name = devCollaborator.name;
  devCredential.email = email;
  devCredential.picture = devCollaborator.picture;
  devCredential.accessToken = "ya29.a0AW4XtxjuHMQDXGCslKDf-OUhfHZDaFap8o9TkDkIGBTHm9dof7Mfo4Cex-qOSJFueNfAkEjiw_7A0g1LpMgvA2Z_AFnawHDFTtiiV6uZx4uspgCnV4DtSftNSPRh_FqZDmkzcDk551oDfSC2qS9GOx9bs9iKSW-g6w4ONjdIaCgYKAdcSARMSFQHGX2Miw6oTJT_DDE_cECxgw4KW3A0175";
  devCredential.refreshToken = "1//05M0YAM9iekJLCgYIARAAGAUSNwF-L9Irr7vNf4AUzgZT5gc-6o5mMR2vvj9SITp6Wot9b9i2WnabeGQ3Ycj6hTDk-cVB4XQCWmk";
  devCredential.scope = "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile openid https://www.googleapis.com/auth/drive";
  devCredential.tokenType = "Bearer";
  devCredential.expiryDate = Date.now() + 3600000; // 1 hora a partir de agora
  devCredential.ativo = true;

  return {
    collaborator: devCollaborator,
    credential: devCredential
  };
} 
