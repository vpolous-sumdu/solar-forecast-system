export interface GenerationForecastItem {
  timestamp: string;
  st_s: number;
  elevation: number;
  azimuth: number;
  predicted_power_watts: number;
  predicted_power_kw: number;
  source: string;
}

export interface GenerationForecastResponse {
  status: string;
  station_id: number;
  count: number;
  data: GenerationForecastItem[];
}
