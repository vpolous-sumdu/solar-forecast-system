import {Injectable, inject} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {GenerationForecastResponse} from '../models/generation.model';

@Injectable({
    providedIn: 'root'
})
export class GenerationService {
    private http = inject(HttpClient);
    private apiUrl = '/forecast/';

    generatePowerForecast(stationId: number, date?: string,
                          weatherSource: string = 'OpenWeatherMap'): Observable<GenerationForecastResponse> {
        let params = new HttpParams().set('weather_source', weatherSource);
        if (date) {
            params = params.set('date', date);
        }
        return this.http.post<GenerationForecastResponse>(`${this.apiUrl}generate/${stationId}`, {}, {params});
    }

    getSavedForecast(stationId: number, date?: string,
                     weatherSource: string = 'OpenWeatherMap'): Observable<GenerationForecastResponse> {
        let params = new HttpParams().set('weather_source', weatherSource);
        if (date) {
            params = params.set('date', date);
        }
        return this.http.get<GenerationForecastResponse>(`${this.apiUrl}${stationId}`, {params});
    }
}