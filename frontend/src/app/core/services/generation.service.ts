import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { GenerationForecastResponse } from '../models/generation.model';

@Injectable({
  providedIn: 'root'
})
export class GenerationService {
  private http = inject(HttpClient);
  private apiUrl = '/forecast/';

  generatePowerForecast(stationId: number, weatherSource: string = 'OpenWeatherMap'): Observable<GenerationForecastResponse> {
    return this.http.post<GenerationForecastResponse>(`${this.apiUrl}generate/${stationId}?weather_source=${weatherSource}`, {});
  }

  getSavedForecast(stationId: number, weatherSource: string = 'OpenWeatherMap'): Observable<GenerationForecastResponse> {
    return this.http.get<GenerationForecastResponse>(`${this.apiUrl}${stationId}?weather_source=${weatherSource}`);
  }
}