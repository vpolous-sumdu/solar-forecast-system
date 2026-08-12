export interface WeatherForecast {
  id: number;
  station_id: number;
  timestamp: string;
  temperature: number;
  cloud_cover: number;
  pressure: number;
  humidity: number;
  wind_speed: number;
  created_at: string;
}
