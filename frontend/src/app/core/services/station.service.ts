import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Station } from '../models/station.model';

@Injectable({
  providedIn: 'root'
})
export class StationService {
  private http = inject(HttpClient);
  private apiUrl = '/stations/';

  getStations(): Observable<Station[]> {
    return this.http.get<Station[]>(this.apiUrl);
  }

  syncStations(): Observable<{ status: string; message: string }> {
    return this.http.post<{ status: string; message: string }>(`${this.apiUrl}sync`, {});
  }
}
