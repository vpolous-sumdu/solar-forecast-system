import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { WeatherForecast } from '../models/weather.model';

@Injectable({
  providedIn: 'root'
})
export class WeatherService {
  private http = inject(HttpClient);
  private apiUrl = '/weather/';

  getWeatherForecast(stationId: number): Observable<WeatherForecast[]> {
    return this.http.get<WeatherForecast[]>(`${this.apiUrl}${stationId}`);
  }

  fetchFreshOpenMeteoWeather(stationId: number): Observable<{ status: string; message: string }> {
    return this.http.post<{ status: string; message: string }>(`${this.apiUrl}fetch-open-meteo/${stationId}`, {});
  }

  fetchFreshOpenWeatherMapWeather(stationId: number): Observable<{ status: string; message: string }> {
    return this.http.post<{ status: string; message: string }>(`${this.apiUrl}fetch-openweathermap/${stationId}`, {});
  }
}
