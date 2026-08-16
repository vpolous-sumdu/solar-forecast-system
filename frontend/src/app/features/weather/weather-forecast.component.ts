import {Component, OnInit, signal, computed, inject} from '@angular/core';
import {DatePipe} from '@angular/common';
import {StationService} from '../../core/services/station.service';
import {WeatherService} from '../../core/services/weather.service';
import {GenerationService} from '../../core/services/generation.service';
import {Station} from '../../core/models/station.model';
import {WeatherForecast} from '../../core/models/weather.model';
import {ChartSeries} from '../../core/models/chart.model';
import {NeuralModel} from '../../core/models/neural-model.model';
import {PowerChartComponent} from '../../shared/components/power-chart/power-chart.component';

@Component({
    selector: 'app-weather-forecast',
    standalone: true,
    imports: [DatePipe, PowerChartComponent],
    templateUrl: './weather-forecast.component.html',
    styleUrl: './weather-forecast.component.css'
})
export class WeatherForecastComponent implements OnInit {
    private stationService = inject(StationService);
    private weatherService = inject(WeatherService);
    private generationService = inject(GenerationService);

    stations = signal<Station[]>([]);
    selectedStationId = signal<number | null>(null);
    selectedDate = signal<string>(this.getDefaultDate());

    selectedWeatherSource = signal<string>('OpenWeatherMap');
    models = signal<NeuralModel[]>([]);
    selectedModelId = signal<number | null>(null);
    loadingModels = signal<boolean>(false);

    forecasts = signal<WeatherForecast[]>([]);
    generationMap = signal<Record<string, { predicted_power_watts: number; predicted_power_kw: number }>>({});

    loading = signal<boolean>(false);
    fetching = signal<boolean>(false);
    fetchingOWM = signal<boolean>(false);
    generating = signal<boolean>(false);
    loadingGen = signal<boolean>(false);
    error = signal<string | null>(null);

    chartLabels = computed<string[]>(() => {
        const list = this.forecasts();
        if (list.length === 0) return [];
        return list.map(w => {
            const d = new Date(w.timestamp);
            const hh = String(d.getUTCHours()).padStart(2, '0');
            return `${hh}:00`;
        });
    });

    chartSeries = computed<ChartSeries[]>(() => {
        const list = this.forecasts();
        const primaryMap = this.generationMap();
        if (list.length === 0 || Object.keys(primaryMap).length === 0) return [];

        const primarySource = this.selectedWeatherSource();
        const primaryValues = list.map(w => {
            const gen = this.getGenerationForItem(w);
            return gen ? gen.predicted_power_kw : 0;
        });

        return [{
            name: `${primarySource} (Прогноз потужності, кВт)`,
            data: primaryValues,
            color: '#2563eb',
            fillColor: 'rgba(37, 99, 235, 0.12)'
        }];
    });

    private getDefaultDate(): string {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        return tomorrow.toISOString().split('T')[0];
    }


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
                    this.loadModels(data[0].id);
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

    loadModels(stationId: number): void {
        this.loadingModels.set(true);
        this.generationService.getNeuralModels(stationId).subscribe({
            next: (modelList) => {
                this.models.set(modelList);
                if (modelList.length > 0) {
                    const active = modelList.find(m => m.is_active) || modelList[0];
                    this.selectedModelId.set(active.id);
                } else {
                    this.selectedModelId.set(null);
                }
                this.loadingModels.set(false);
            },
            error: () => {
                this.models.set([]);
                this.selectedModelId.set(null);
                this.loadingModels.set(false);
            }
        });
    }

    onStationChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        const stationId = Number(select.value);
        this.selectedStationId.set(stationId);
        this.generationMap.set({});
        this.loadModels(stationId);
        this.loadWeather(stationId);
    }

    onModelChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        const modelId = Number(select.value);
        this.selectedModelId.set(modelId);
        this.generationMap.set({});
        const stationId = this.selectedStationId();
        if (stationId) {
            this.loadWeather(stationId);
        }
    }

    onDateChange(event: Event): void {
        const input = event.target as HTMLInputElement;
        if (input.value) {
            this.selectedDate.set(input.value);
            this.generationMap.set({});
            const stationId = this.selectedStationId();
            if (stationId) {
                this.loadWeather(stationId);
            }
        }
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
        const date = this.selectedDate();

        this.weatherService.getWeatherForecast(stationId, date).subscribe({
            next: (weatherData) => {
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
        const date = this.selectedDate();
        const modelId = this.selectedModelId() || undefined;

        this.generationService.getSavedForecast(stationId, date, source, modelId).subscribe({
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
        } else if (source === 'Open-Meteo-Archive') {
            this.fetchFreshArchiveWeather();
        } else {
            this.fetchFreshWeather();
        }
    }

    fetchFreshWeather(): void {
        const stationId = this.selectedStationId();
        if (!stationId) return;

        this.fetching.set(true);
        this.error.set(null);
        const date = this.selectedDate();

        this.weatherService.fetchFreshOpenMeteoWeather(stationId, date).subscribe({
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

    fetchFreshArchiveWeather(): void {
        const stationId = this.selectedStationId();
        if (!stationId) return;

        this.fetching.set(true);
        this.error.set(null);
        const date = this.selectedDate();

        this.weatherService.fetchFreshOpenMeteoArchiveWeather(stationId, date).subscribe({
            next: () => {
                this.fetching.set(false);
                this.generationMap.set({});
                this.loadWeather(stationId);
            },
            error: () => {
                this.error.set('Помилка завантаження реальної погоди з Open-Meteo Archive');
                this.fetching.set(false);
            }
        });
    }

    fetchFreshOWMWeather(): void {
        const stationId = this.selectedStationId();
        if (!stationId) return;

        this.fetchingOWM.set(true);
        this.error.set(null);
        const date = this.selectedDate();

        this.weatherService.fetchFreshOpenWeatherMapWeather(stationId, date).subscribe({
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
        const date = this.selectedDate();
        this.generating.set(true);
        this.error.set(null);

        // Якщо погоду для обраного джерела ще не збережено в компоненту, спершу підтягуємо її
        if (this.forecasts().length === 0) {
            const fetchObs = (source === 'OpenWeatherMap')
                ? this.weatherService.fetchFreshOpenWeatherMapWeather(stationId, date)
                : (source === 'Open-Meteo-Archive')
                    ? this.weatherService.fetchFreshOpenMeteoArchiveWeather(stationId, date)
                    : this.weatherService.fetchFreshOpenMeteoWeather(stationId, date);

            fetchObs.subscribe({
                next: () => {
                    this.executeGeneration(stationId, date, source);
                },
                error: () => {
                    this.generating.set(false);
                    this.error.set(`Не вдалося завантажити погоду для ${source}`);
                }
            });
            return;
        }

        this.executeGeneration(stationId, date, source);
    }

    private executeGeneration(stationId: number, date: string, source: string): void {
        const modelId = this.selectedModelId() || undefined;
        this.generationService.generatePowerForecast(stationId, date, source, modelId).subscribe({
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
                this.loadWeather(stationId);
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
