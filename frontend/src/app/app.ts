import { Component, OnInit, signal, inject } from '@angular/core';
import { StationService, Station } from './station.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [],
  templateUrl: './app.html'
})
export class AppComponent implements OnInit {
  private stationService = inject(StationService);

  stations = signal<Station[]>([]);
  loading = signal<boolean>(true);
  error = signal<string | null>(null);

  ngOnInit(): void {
    this.loadStations();
  }

  loadStations(): void {
    this.loading.set(true);
    this.error.set(null);

    this.stationService.getStations().subscribe({
      next: (data) => {
        this.stations.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.message || 'Помилка підключення');
        this.loading.set(false);
      }
    });
  }
}
