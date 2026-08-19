import {ChangeDetectionStrategy, Component, computed, inject, OnInit, signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {forkJoin, of} from 'rxjs';
import {catchError} from 'rxjs/operators';
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
    changeDetection: ChangeDetectionStrategy.OnPush,
    imports: [CommonModule, PowerChartComponent],
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

    models = signal<NeuralModel[]>([]);
    selectedModelId = signal<number | null>(null);
    loadingModels = signal<boolean>(false);

    forecasts = signal<WeatherForecast[]>([]);
    allSourcesWeatherMap = signal<Record<string, Record<string, WeatherForecast>>>({});
    allSourcesGenerationMap = signal<Record<string, Record<string, {
        predicted_power_watts: number;
        predicted_power_kw: number
    }>>>({});

    loading = signal<boolean>(false);
    fetching = signal<boolean>(false);
    generating = signal<boolean>(false);
    loadingGen = signal<boolean>(false);
    fetchingSources = signal<string[]>([]);
    generatingSources = signal<string[]>([]);
    error = signal<string | null>(null);

    isSourceFetching(source: string): boolean {
        return this.fetchingSources().includes(source);
    }

    isSourceGenerating(source: string): boolean {
        return this.generatingSources().includes(source);
    }


    // Доступні опції джерел прогнозів погоди (включаючи архівну фактичну погоду)
    readonly weatherSourceOptions = [
        {id: 'OpenWeatherMap', label: 'OpenWeatherMap', color: '#2563eb'},
        {id: 'Open-Meteo', label: 'Open-Meteo', color: '#f59e0b'},
        {id: 'Visual-Crossing', label: 'Visual-Crossing', color: '#10b981'},
        {id: 'Open-Meteo-Archive', label: 'Open-Meteo (Фактична погода)', color: '#8b5cf6'}
    ];

    selectedSources = signal<string[]>(['OpenWeatherMap', 'Open-Meteo', 'Visual-Crossing']);

    isArchiveDisabled = computed<boolean>(() => {
        const selected = this.selectedDate();
        const today = this.getTodayDate();
        return selected >= today;
    });

    isSourceDisabled(sourceId: string): boolean {
        if (sourceId === 'Open-Meteo-Archive') {
            return this.isArchiveDisabled();
        }
        return false;
    }

    isSourceSelected(sourceId: string): boolean {
        return this.selectedSources().includes(sourceId);
    }

    toggleSource(sourceId: string): void {
        if (this.isSourceDisabled(sourceId)) return;

        const current = this.selectedSources();
        if (current.includes(sourceId)) {
            this.selectedSources.set(current.filter(s => s !== sourceId));
        } else {
            this.selectedSources.set([...current, sourceId]);
        }
    }

    // Джерела, для яких ще не завантажено погоду в БД на цю дату
    sourcesNeedingWeather = computed<string[]>(() => {
        const selected = this.selectedSources();
        if (selected.length === 0) return [];
        const allMap = this.allSourcesWeatherMap();
        return selected.filter(src => {
            const points = allMap[src];
            return !points || Object.keys(points).length === 0;
        });
    });

    isWeatherComplete = computed<boolean>(() => {
        const selected = this.selectedSources();
        if (selected.length === 0) return true;
        return this.sourcesNeedingWeather().length === 0;
    });

    weatherButtonLabel = computed<string>(() => {
        if (this.fetching()) {
            return 'Завантаження...';
        }
        const needed = this.sourcesNeedingWeather();
        const selected = this.selectedSources();

        if (selected.length === 0) {
            return 'Оберіть джерело';
        }
        if (needed.length === 0) {
            return 'Погода завантажена для всіх';
        }
        if (needed.length === selected.length) {
            return 'Завантажити погоду (вибрані)';
        }
        return `Завантажити погоду (${needed.join(', ')})`;
    });

    // Джерела, для яких ще не сформовано прогноз генерації у БД
    sourcesNeedingGeneration = computed<string[]>(() => {
        const selected = this.selectedSources();
        if (selected.length === 0) return [];
        const allMap = this.allSourcesGenerationMap();
        return selected.filter(src => {
            const points = allMap[src];
            return !points || Object.keys(points).length === 0;
        });
    });


    isGenerationComplete = computed<boolean>(() => {
        const selected = this.selectedSources();
        if (selected.length === 0) return true;
        return this.sourcesNeedingGeneration().length === 0;
    });

    generationButtonLabel = computed<string>(() => {
        if (this.generating()) {
            return 'Розрахунок...';
        }
        const needed = this.sourcesNeedingGeneration();
        const selected = this.selectedSources();

        if (selected.length === 0) {
            return 'Оберіть джерело';
        }
        if (needed.length === 0) {
            return 'Прогноз сформовано для всіх';
        }
        if (needed.length === selected.length) {
            return 'Сформувати прогноз генерації';
        }
        return `Сформувати прогноз (${needed.join(', ')})`;
    });

    availableSourcesWithData = computed<string[]>(() => {
        const selected = this.selectedSources();
        const order = ['OpenWeatherMap', 'Open-Meteo', 'Visual-Crossing', 'Open-Meteo-Archive'];
        return order.filter(s => selected.includes(s));
    });

    hourlyTimestamps = computed<string[]>(() => {
        const wMap = this.allSourcesWeatherMap();
        const gMap = this.allSourcesGenerationMap();
        const keys = new Set<string>();

        for (const src of Object.keys(wMap)) {
            for (const t of Object.keys(wMap[src])) {
                keys.add(t);
            }
        }
        for (const src of Object.keys(gMap)) {
            for (const t of Object.keys(gMap[src])) {
                keys.add(t);
            }
        }
        return Array.from(keys).sort();
    });

    chartLabels = computed<string[]>(() => {
        if (this.selectedSources().length === 0) return [];
        const list = this.hourlyTimestamps();
        if (list.length === 0) return [];
        return list.map(iso => {
            const d = new Date(iso);
            const hh = String(d.getUTCHours()).padStart(2, '0');
            return `${hh}:00`;
        });
    });

    chartSeries = computed<ChartSeries[]>(() => {
        if (this.selectedSources().length === 0) return [];
        const timestamps = this.hourlyTimestamps();
        if (timestamps.length === 0) return [];

        const allMap = this.allSourcesGenerationMap();
        const activeSources = this.availableSourcesWithData();
        if (activeSources.length === 0) return [];

        const sourceColors: Record<string, { color: string; fill: string }> = {
            'OpenWeatherMap': {color: '#2563eb', fill: 'rgba(37, 99, 235, 0.08)'}, // Синій
            'Open-Meteo': {color: '#f59e0b', fill: 'rgba(245, 158, 11, 0.08)'},     // Оранжевий
            'Visual-Crossing': {color: '#10b981', fill: 'rgba(16, 185, 129, 0.08)'},// Зелений
            'Open-Meteo-Archive': {color: '#8b5cf6', fill: 'rgba(139, 92, 246, 0.08)'} // Фіолетовий
        };

        return activeSources
            .filter(src => allMap[src] && Object.keys(allMap[src]).length > 0)
            .map(src => {
                const srcMap = allMap[src] || {};
                const values = timestamps.map(iso => {
                    const gen = srcMap[iso];
                    return gen ? gen.predicted_power_kw : 0;
                });
                const colorConfig = sourceColors[src] || {color: '#6b7280', fill: 'rgba(107, 114, 128, 0.08)'};
                return {
                    name: `${src} (Прогноз потужності, кВт)`,
                    data: values,
                    color: colorConfig.color,
                    fillColor: colorConfig.fill
                };
            });
    });


    private getDefaultDate(): string {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        return tomorrow.toISOString().split('T')[0];
    }

    getTodayDate(): string {
        const today = new Date();
        return today.toISOString().split('T')[0];
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
                    const currentSelected = this.selectedModelId();
                    const exists = modelList.some(m => m.id === currentSelected);
                    if (!currentSelected || !exists) {
                        this.selectedModelId.set(modelList[0].id);
                    }
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
        this.allSourcesGenerationMap.set({});
        this.allSourcesWeatherMap.set({});
        this.forecasts.set([]);
        this.loadModels(stationId);
        this.loadWeather(stationId);
    }

    onModelChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        const modelId = Number(select.value);
        this.selectedModelId.set(modelId);
        this.allSourcesGenerationMap.set({});
        const stationId = this.selectedStationId();
        if (stationId) {
            this.loadWeather(stationId);
        }
    }

    onDateChange(event: Event): void {
        const input = event.target as HTMLInputElement;
        if (input.value) {
            this.selectedDate.set(input.value);
            // Якщо обрано сьогодні або майбутню дату — знімаємо прапорець з архіву, оскільки він недоступний
            if (this.isArchiveDisabled() && this.selectedSources().includes('Open-Meteo-Archive')) {
                this.selectedSources.set(this.selectedSources().filter(s => s !== 'Open-Meteo-Archive'));
            }
            this.allSourcesGenerationMap.set({});
            this.allSourcesWeatherMap.set({});
            this.forecasts.set([]);
            const stationId = this.selectedStationId();
            if (stationId) {
                this.loadWeather(stationId);
            }
        }
    }

    loadWeather(stationId: number): void {
        if (this.hourlyTimestamps().length === 0) {
            this.loading.set(true);
        }
        this.error.set(null);
        const date = this.selectedDate();

        this.weatherService.getWeatherForecast(stationId, date).subscribe({
            next: (weatherData) => {
                // Групуємо всі отримані метеозаписи за джерелами та ISO часовими мітками
                const weatherMap: Record<string, Record<string, WeatherForecast>> = {};
                for (const w of weatherData) {
                    const isoKey = new Date(w.timestamp).toISOString();
                    const src = w.source || 'Open-Meteo';
                    if (!weatherMap[src]) {
                        weatherMap[src] = {};
                    }
                    weatherMap[src][isoKey] = w;
                }
                this.allSourcesWeatherMap.set(weatherMap);

                // Вибираємо 24 годинні записи для сумісності
                let primaryRows = weatherData.filter(w => w.source === 'OpenWeatherMap');
                if (primaryRows.length === 0) {
                    primaryRows = weatherData.filter(w => w.source === 'Open-Meteo');
                }
                if (primaryRows.length === 0) {
                    primaryRows = weatherData.filter(w => w.source === 'Visual-Crossing');
                }
                if (primaryRows.length === 0) {
                    primaryRows = weatherData.filter(w => w.source === 'Open-Meteo-Archive');
                }
                if (primaryRows.length === 0 && weatherData.length > 0) {
                    primaryRows = weatherData.slice(0, 24);
                }
                this.forecasts.set(primaryRows);
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
        const date = this.selectedDate();
        const modelId = this.selectedModelId() || undefined;

        this.generationService.getSavedForecast(stationId, date, 'ALL', modelId).subscribe({
            next: (res) => {
                const fullMap: Record<string, Record<string, {
                    predicted_power_watts: number;
                    predicted_power_kw: number
                }>> = {};

                for (const item of res.data) {
                    const isoKey = new Date(item.timestamp).toISOString();
                    const itemSrc = item.source || 'OpenWeatherMap';
                    if (!fullMap[itemSrc]) {
                        fullMap[itemSrc] = {};
                    }
                    fullMap[itemSrc][isoKey] = {
                        predicted_power_watts: item.predicted_power_watts,
                        predicted_power_kw: item.predicted_power_kw
                    };
                }

                this.allSourcesGenerationMap.set(fullMap);
                this.loadingGen.set(false);
            },
            error: () => {
                this.allSourcesGenerationMap.set({});
                this.loadingGen.set(false);
            }
        });
    }

    fetchSelectedWeather(forceAll: boolean = false): void {
        const stationId = this.selectedStationId();
        if (!stationId) return;

        const targetSources = forceAll ? this.selectedSources() : this.sourcesNeedingWeather();
        if (targetSources.length === 0) return;

        this.fetching.set(true);
        this.fetchingSources.set(targetSources);
        this.error.set(null);
        const date = this.selectedDate();

        const requests = [];
        if (targetSources.includes('OpenWeatherMap')) {
            requests.push(this.weatherService.fetchFreshOpenWeatherMapWeather(stationId, date).pipe(catchError(() => of(null))));
        }
        if (targetSources.includes('Open-Meteo')) {
            requests.push(this.weatherService.fetchFreshOpenMeteoWeather(stationId, date).pipe(catchError(() => of(null))));
        }
        if (targetSources.includes('Visual-Crossing')) {
            requests.push(this.weatherService.fetchFreshVisualCrossingWeather(stationId, date).pipe(catchError(() => of(null))));
        }
        if (targetSources.includes('Open-Meteo-Archive')) {
            requests.push(this.weatherService.fetchFreshOpenMeteoArchiveWeather(stationId, date).pipe(catchError(() => of(null))));
        }

        forkJoin(requests).subscribe({
            next: () => {
                this.fetching.set(false);
                this.fetchingSources.set([]);
                this.loadWeather(stationId);
            },
            error: () => {
                this.fetching.set(false);
                this.fetchingSources.set([]);
                this.loadWeather(stationId);
            }
        });
    }

    generatePowerForecast(forceAll: boolean = false): void {
        const stationId = this.selectedStationId();
        if (!stationId) return;

        const targetSources = forceAll ? this.selectedSources() : this.sourcesNeedingGeneration();
        if (targetSources.length === 0) return;

        const date = this.selectedDate();
        const modelId = this.selectedModelId() || undefined;

        this.generating.set(true);
        this.generatingSources.set(targetSources);
        this.error.set(null);

        const requests = targetSources.map(src =>
            this.generationService.generatePowerForecast(stationId, date, src, modelId).pipe(catchError(() => of(null)))
        );

        forkJoin(requests).subscribe({
            next: () => {
                this.generating.set(false);
                this.generatingSources.set([]);
                this.loadWeather(stationId);
            },
            error: () => {
                this.generating.set(false);
                this.generatingSources.set([]);
                this.loadWeather(stationId);
            }
        });
    }


    getTimeIntervalLabel(isoTimestamp: string): string {
        const d = new Date(isoTimestamp);
        const startHour = d.getUTCHours();
        const endHour = (startHour + 1) % 24;
        const startStr = String(startHour).padStart(2, '0') + ':00';
        const endStr = String(endHour).padStart(2, '0') + ':00';
        return `${startStr} - ${endStr}`;
    }

    getWeatherForSource(isoTimestamp: string, source: string): WeatherForecast | null {

        const srcMap = this.allSourcesWeatherMap()[source];
        return srcMap ? srcMap[isoTimestamp] || null : null;
    }

    getGenerationForSourceByIso(isoTimestamp: string, source: string): {
        predicted_power_watts: number;
        predicted_power_kw: number
    } | null {
        const srcMap = this.allSourcesGenerationMap()[source];
        return srcMap ? srcMap[isoTimestamp] || null : null;
    }

    getAstroForTimestamp(isoTimestamp: string): {
        st_s: number;
        h_svetl: number;
        azimuth: number;
        elevation: number
    } | null {
        const wMap = this.allSourcesWeatherMap();
        for (const src of Object.keys(wMap)) {
            const w = wMap[src][isoTimestamp];
            if (w) {
                return {
                    st_s: w.st_s,
                    h_svetl: w.h_svetl,
                    azimuth: w.azimuth,
                    elevation: w.elevation
                };
            }
        }
        return null;
    }

    getSourceColor(source: string): string {

        switch (source) {
            case 'OpenWeatherMap':
                return '#2563eb'; // Синій
            case 'Open-Meteo':
                return '#f59e0b';     // Оранжевий
            case 'Visual-Crossing':
                return '#10b981';// Зелений
            case 'Open-Meteo-Archive':
                return '#8b5cf6'; // Фіолетовий
            default:
                return '#6b7280';
        }
    }

    getSourceBadgeClass(source: string): string {
        switch (source) {
            case 'OpenWeatherMap':
                return 'badge-owm';       // Синій фон і текст
            case 'Open-Meteo':
                return 'badge-openmeteo';     // Оранжевий фон і текст
            case 'Visual-Crossing':
                return 'badge-visualcrossing'; // Зелений фон і текст
            case 'Open-Meteo-Archive':
                return 'badge-archive'; // Фіолетовий фон і текст
            default:
                return 'badge-default';
        }
    }
}
