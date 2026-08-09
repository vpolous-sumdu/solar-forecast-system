import { Component, OnInit, signal, inject } from '@angular/core';
import { StationService } from '../../core/services/station.service';
import { Station } from '../../core/models/station.model';

@Component({
  selector: 'app-station-list',
  standalone: true,
  imports: [],
  templateUrl: './station-list.component.html'
})
export class StationListComponent implements OnInit {
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
