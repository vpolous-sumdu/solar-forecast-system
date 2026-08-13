export interface WeatherForecast {
  id: number;
  station_id: number;
  timestamp: string;
  temperature: number;
  cloud_cover: number;
  pressure: number;
  humidity: number;
  wind_speed: number;
  source: string;
  st_s: number;
  h_svetl: number;
  azimuth: number;
  elevation: number;
  day_of_week: number;
  ww: number;
  created_at: string;
}
