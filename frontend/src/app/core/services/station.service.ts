import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {Station} from '../models/station.model';

@Injectable({
    providedIn: 'root'
})
export class StationService {
    private http = inject(HttpClient);

    getStations(): Observable<Station[]> {
        return this.http.get<Station[]>('/api/v1/stations');
    }

    syncStations(): Observable<{ status: string; message: string }> {
        return this.http.post<{ status: string; message: string }>('/api/v1/stations/sync', {});
    }
}
