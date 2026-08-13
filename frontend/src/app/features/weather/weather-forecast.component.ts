import { Component, OnInit, signal, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { StationService } from '../../core/services/station.service';
import { WeatherService } from '../../core/services/weather.service';
import { GenerationService } from '../../core/services/generation.service';
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
  private generationService = inject(GenerationService);

  stations = signal<Station[]>([]);
  selectedStationId = signal<number | null>(null);

  selectedWeatherSource = signal<string>('OpenWeatherMap');

  forecasts = signal<WeatherForecast[]>([]);
  generationMap = signal<Record<string, { predicted_power_watts: number; predicted_power_kw: number }>>({});

  loading = signal<boolean>(false);
  fetching = signal<boolean>(false);
  fetchingOWM = signal<boolean>(false);
  generating = signal<boolean>(false);
  loadingGen = signal<boolean>(false);
  error = signal<string | null>(null);

  ngOnInit(): void {
    this.loadStations();
  }

  loadStations(): void {
    this.loading.set(true);
    this.stationService.getStations().subscribe({
      next: (data) => {
        this.stations.set(data);
        if (data.length > 0) {
          this.selectedStationId.set(data[0].id);
          this.loadWeather(data[0].id);
        } else {
          this.loading.set(false);
        }
      },
      error: () => {
        this.error.set('Не вдалося завантажити список СЕС');
        this.loading.set(false);
      }
    });
  }

  onStationChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const stationId = Number(select.value);
    this.selectedStationId.set(stationId);
    this.generationMap.set({});
    this.loadWeather(stationId);
  }

  onWeatherSourceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedWeatherSource.set(select.value);
    this.generationMap.set({});
    const stationId = this.selectedStationId();
    if (stationId) {
      this.loadWeather(stationId);
    }
  }

  loadWeather(stationId: number): void {
    this.loading.set(true);
    this.error.set(null);

    this.weatherService.getWeatherForecast(stationId).subscribe({
      next: (weatherData) => {
        // Фільтруємо збережену погоду СТРОГО під обране джерело (OpenWeatherMap / Open-Meteo)
        const source = this.selectedWeatherSource();
        const filtered = weatherData.filter(w => w.source === source);
        this.forecasts.set(filtered);
        this.loading.set(false);
        this.loadSavedGeneration(stationId);

      },
      error: () => {
        this.error.set('Не вдалося отримати збережений прогноз погоди');
        this.loading.set(false);
      }
    });
  }

  loadSavedGeneration(stationId: number): void {
    this.loadingGen.set(true);
    const source = this.selectedWeatherSource();
    this.generationService.getSavedForecast(stationId, source).subscribe({
      next: (res) => {
        const map: Record<string, { predicted_power_watts: number; predicted_power_kw: number }> = {};
        for (const item of res.data) {
          const isoKey = new Date(item.timestamp).toISOString();
          map[isoKey] = {
            predicted_power_watts: item.predicted_power_watts,
            predicted_power_kw: item.predicted_power_kw
          };
        }
        this.generationMap.set(map);
        this.loadingGen.set(false);
      },
      error: () => {
        this.loadingGen.set(false);
      }
    });
  }

  fetchSelectedWeather(): void {
    const source = this.selectedWeatherSource();
    if (source === 'OpenWeatherMap') {
      this.fetchFreshOWMWeather();
    } else {
      this.fetchFreshWeather();
    }
  }

  fetchFreshWeather(): void {
    const stationId = this.selectedStationId();
    if (!stationId) return;

    this.fetching.set(true);
    this.error.set(null);

    this.weatherService.fetchFreshOpenMeteoWeather(stationId).subscribe({
      next: () => {
        this.fetching.set(false);
        this.generationMap.set({});
        this.loadWeather(stationId);
      },
      error: () => {
        this.error.set('Помилка завантаження погоди з Open-Meteo');
        this.fetching.set(false);
      }
    });
  }

  fetchFreshOWMWeather(): void {
    const stationId = this.selectedStationId();
    if (!stationId) return;

    this.fetchingOWM.set(true);
    this.error.set(null);

    this.weatherService.fetchFreshOpenWeatherMapWeather(stationId).subscribe({
      next: () => {
        this.fetchingOWM.set(false);
        this.generationMap.set({});
        this.loadWeather(stationId);
      },
      error: () => {
        this.error.set('Помилка завантаження погоди з OpenWeatherMap');
        this.fetchingOWM.set(false);
      }
    });
  }

  generatePowerForecast(): void {
    const stationId = this.selectedStationId();
    if (!stationId) return;

    const source = this.selectedWeatherSource();
    this.generating.set(true);
    this.error.set(null);

    this.generationService.generatePowerForecast(stationId, source).subscribe({
      next: (res) => {
        const map: Record<string, { predicted_power_watts: number; predicted_power_kw: number }> = {};
        for (const item of res.data) {
          const isoKey = new Date(item.timestamp).toISOString();
          map[isoKey] = {
            predicted_power_watts: item.predicted_power_watts,
            predicted_power_kw: item.predicted_power_kw
          };
        }
        this.generationMap.set(map);
        this.generating.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Помилка розрахунку прогнозу генерації');
        this.generating.set(false);
      }
    });
  }

  getGenerationForItem(w: WeatherForecast): { predicted_power_watts: number; predicted_power_kw: number } | null {
    const key = new Date(w.timestamp).toISOString();
    return this.generationMap()[key] || null;
  }
}
