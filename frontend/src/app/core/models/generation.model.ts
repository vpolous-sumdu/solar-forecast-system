export interface GenerationForecast {
  id: number;
  station_id: number;
  model_id: number | null;
  timestamp: string;
  predicted_power_kw: number;
  created_at: string;
}
