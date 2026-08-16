import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {WeatherForecast} from '../models/weather.model';

@Injectable({
    providedIn: 'root'
})
export class WeatherService {
    private http = inject(HttpClient);
    private apiUrl = '/weather/';

    getWeatherForecast(stationId: number, date?: string): Observable<WeatherForecast[]> {
        let params = new HttpParams();
        if (date) {
            params = params.set('date', date);
        }
        return this.http.get<WeatherForecast[]>(`${this.apiUrl}${stationId}`, {params});
    }

    fetchFreshOpenMeteoWeather(stationId: number, date?: string): Observable<{ status: string; message: string }> {
        let params = new HttpParams();
        if (date) {
            params = params.set('date', date);
        }
        return this.http.post<{
            status: string;
            message: string
        }>(`${this.apiUrl}fetch-open-meteo/${stationId}`, {}, {params});
    }

    fetchFreshOpenWeatherMapWeather(stationId: number, date?: string): Observable<{ status: string; message: string }> {
        let params = new HttpParams();
        if (date) {
            params = params.set('date', date);
        }
        return this.http.post<{
            status: string;
            message: string
        }>(`${this.apiUrl}fetch-openweathermap/${stationId}`, {}, {params});
    }

    fetchFreshOpenMeteoArchiveWeather(stationId: number, date?: string): Observable<{
        status: string;
        message: string
    }> {
        let params = new HttpParams();
        if (date) {
            params = params.set('date', date);
        }
        return this.http.post<{
            status: string;
            message: string
        }>(`${this.apiUrl}fetch-open-meteo-archive/${stationId}`, {}, {params});
    }
}

