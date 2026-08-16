import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {ComparisonDatesResponse, ComparisonResponse} from '../models/comparison.model';

@Injectable({
    providedIn: 'root'
})
export class ComparisonService {
    private http = inject(HttpClient);
    private apiUrl = '/comparison/';

    getComparison(
        stationId: number,
        date?: string,
        weatherSource: string = 'OpenWeatherMap',
        modelId?: number,
        forceSync: boolean = false
    ): Observable<ComparisonResponse> {
        let params = new HttpParams()
            .set('weather_source', weatherSource)
            .set('force_sync', forceSync.toString());

        if (date) {
            params = params.set('date', date);
        }
        if (modelId !== undefined && modelId !== null) {
            params = params.set('model_id', modelId.toString());
        }

        return this.http.get<ComparisonResponse>(`${this.apiUrl}${stationId}`, {params});
    }

    getAvailableDates(stationId: number): Observable<ComparisonDatesResponse> {
        return this.http.get<ComparisonDatesResponse>(`${this.apiUrl}${stationId}/dates`);
    }

    syncActual(stationId: number, date: string): Observable<any> {
        const params = new HttpParams().set('date', date);
        return this.http.post(`${this.apiUrl}sync-actual/${stationId}`, {}, {params});
    }
}
