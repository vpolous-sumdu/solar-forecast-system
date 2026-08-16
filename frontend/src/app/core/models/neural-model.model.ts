export interface NeuralModel {
  id: number;
  station_id: number;
  name: string;
  code: string;
  is_active: boolean;
  created_at?: string;
}
