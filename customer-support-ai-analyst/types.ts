export interface ChatMessage {
  sender: 'user' | 'ai';
  text: string;
  file?: {
    name: string;
    type: string;
  };
}

export enum AppStep {
  SelectDataSource = 'SELECT_DATA_SOURCE',
  UploadData = 'UPLOAD_DATA',
  ConfirmSchema = 'CONFIRM_SCHEMA',
  Chat = 'CHAT',
}