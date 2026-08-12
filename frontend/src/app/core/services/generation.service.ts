import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { GenerationForecast } from '../models/generation.model';

@Injectable({
  providedIn: 'root'
})
export class GenerationService {
  private http = inject(HttpClient);
  private apiUrl = 'https://solar-forecast-system.onrender.com/api/v1/forecast/';

  getGenerationForecast(stationId: number): Observable<GenerationForecast[]> {
    return this.http.get<GenerationForecast[]>(`${this.apiUrl}${stationId}`);
  }

  generatePowerForecast(stationId: number): Observable<GenerationForecast[]> {
    return this.http.post<GenerationForecast[]>(`${this.apiUrl}generate/${stationId}`, {});
  }
}
