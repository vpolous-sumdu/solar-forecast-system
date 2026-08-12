import { Component, OnInit, signal, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { StationService } from '../../core/services/station.service';
import { WeatherService } from '../../core/services/weather.service';
import { Station } from '../../core/models/station.model';
import { WeatherForecast } from '../../core/models/weather.model';

@Component({
  selector: 'app-weather-forecast',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './weather-forecast.component.html',
  styleUrl: './weather-forecast.component.css'
})
export class WeatherForecastComponent implements OnInit {
  private stationService = inject(StationService);
  private weatherService = inject(WeatherService);

  stations = signal<Station[]>([]);
  selectedStationId = signal<number | null>(null);

  forecasts = signal<WeatherForecast[]>([]);
  loading = signal<boolean>(false);
  fetching = signal<boolean>(false);
  error = signal<string | null>(null);

  ngOnInit(): void {
    this.loadStations();
  }

  loadStations(): void {
    this.stationService.getStations().subscribe({
      next: (data) => {
        this.stations.set(data);
        if (data.length > 0) {
          this.selectedStationId.set(data[0].id);
          this.loadWeather(data[0].id);
        }
      },
      error: (err) => {
        this.error.set('Не вдалося завантажити список СЕС');
      }
    });
  }

  onStationChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const stationId = Number(select.value);
    this.selectedStationId.set(stationId);
    this.loadWeather(stationId);
  }

  loadWeather(stationId: number): void {
    this.loading.set(true);
    this.error.set(null);

    this.weatherService.getWeatherForecast(stationId).subscribe({
      next: (data) => {
        this.forecasts.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set('Не вдалося отримати збережений прогноз погоди');
        this.loading.set(false);
      }
    });
  }

  fetchFreshWeather(): void {
    const stationId = this.selectedStationId();
    if (!stationId) return;

    this.fetching.set(true);
    this.error.set(null);

    this.weatherService.fetchFreshWeather(stationId).subscribe({
      next: () => {
        this.fetching.set(false);
        this.loadWeather(stationId);
      },
      error: (err) => {
        this.error.set('Помилка завантаження погоди з Open-Meteo');
        this.fetching.set(false);
      }
    });
  }
}
