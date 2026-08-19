import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {GenerationForecastResponse} from '../models/generation.model';
import {NeuralModel} from '../models/neural-model.model';

@Injectable({
    providedIn: 'root'
})
export class GenerationService {
    private http = inject(HttpClient);

    getNeuralModels(stationId: number): Observable<NeuralModel[]> {
        return this.http.get<NeuralModel[]>(`/api/v1/forecast/models/${stationId}`);
    }

    generatePowerForecast(stationId: number, date?: string, weatherSource: string = 'OpenWeatherMap',
                          modelId?: number): Observable<GenerationForecastResponse> {
        let params = new HttpParams().set('weather_source', weatherSource);
        if (date) {
            params = params.set('date', date);
        }
        if (modelId !== undefined && modelId !== null) {
            params = params.set('model_id', modelId.toString());
        }
        return this.http.post<GenerationForecastResponse>(`/api/v1/forecast/generate/${stationId}`, {}, {params});
    }

    getSavedForecast(
        stationId: number,
        date?: string,
        weatherSource: string = 'ALL',
        modelId?: number
    ): Observable<GenerationForecastResponse> {
        let params = new HttpParams().set('weather_source', weatherSource);
        if (date) {
            params = params.set('date', date);
        }
        if (modelId !== undefined && modelId !== null) {
            params = params.set('model_id', modelId.toString());
        }
        return this.http.get<GenerationForecastResponse>(`/api/v1/forecast/${stationId}`, {params});
    }
}