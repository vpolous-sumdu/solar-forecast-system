import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Station {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  installed_capacity_kw: number;
  created_at: string;
}

@Injectable({
  providedIn: 'root'
})
export class StationService {
  private apiUrl = 'https://solar-forecast-system.onrender.com/api/v1/stations/';

  constructor(private http: HttpClient) {}

  getStations(): Observable<Station[]> {
    return this.http.get<Station[]>(this.apiUrl);
  }
}
