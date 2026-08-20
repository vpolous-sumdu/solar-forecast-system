import {ChangeDetectionStrategy, Component, computed, inject, OnInit, signal} from '@angular/core';
import {CommonModule, DecimalPipe} from '@angular/common';
import {StationService} from '../../core/services/station.service';
import {ComparisonService} from '../../core/services/comparison.service';
import {GenerationService} from '../../core/services/generation.service';
import {Station} from '../../core/models/station.model';
import {ComparisonResponse, HourlyComparisonItem, HourlySourceData} from '../../core/models/comparison.model';
import {ChartSeries} from '../../core/models/chart.model';
import {NeuralModel} from '../../core/models/neural-model.model';
import {PowerChartComponent} from '../../shared/components/power-chart/power-chart.component';

@Component({
    selector: 'app-comparison',
    standalone: true,
    changeDetection: ChangeDetectionStrategy.OnPush,
    imports: [CommonModule, DecimalPipe, PowerChartComponent],
    templateUrl: './comparison.component.html',
    styleUrl: './comparison.component.css'
})
export class ComparisonComponent implements OnInit {
    private stationService = inject(StationService);
    private comparisonService = inject(ComparisonService);
    private generationService = inject(GenerationService);

    stations = signal<Station[]>([]);
    selectedStationId = signal<number | null>(null);
    selectedDate = signal<string>(this.getDefaultDate());
    availableDates = signal<string[]>([]);
    models = signal<NeuralModel[]>([]);
    selectedModelId = signal<number | null>(null);
    loadingModels = signal<boolean>(false);

    readonly weatherSourceOptions = [
        {id: 'OpenWeatherMap', label: 'OpenWeatherMap', color: '#2563eb'},
        {id: 'Open-Meteo', label: 'Open-Meteo', color: '#f59e0b'},
        {id: 'Visual-Crossing', label: 'Visual-Crossing', color: '#10b981'},
        {id: 'Open-Meteo-Archive', label: 'Open-Meteo (Фактична погода)', color: '#8b5cf6'}
    ];

    selectedSources = signal<string[]>(['OpenWeatherMap', 'Open-Meteo', 'Visual-Crossing']);

    comparisonData = signal<ComparisonResponse | null>(null);
    loading = signal<boolean>(false);
    syncing = signal<boolean>(false);
    error = signal<string | null>(null);

    private getDefaultDate(): string {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        return yesterday.toISOString().split('T')[0];
    }

    getTodayDate(): string {
        const today = new Date();
        return today.toISOString().split('T')[0];
    }

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

    availableSourcesWithData = computed<string[]>(() => {
        const selected = this.selectedSources();
        const data = this.comparisonData();
        const presentSources = data?.available_sources || [];
        const order = ['OpenWeatherMap', 'Open-Meteo', 'Visual-Crossing', 'Open-Meteo-Archive'];
        return order.filter(s => selected.includes(s) && (presentSources.length === 0 || presentSources.includes(s)));
    });

    chartLabels = computed<string[]>(() => {
        const data = this.comparisonData();
        if (!data || !data.hourly_data || data.hourly_data.length === 0) return [];
        return data.hourly_data.map(item => `${String(item.hour).padStart(2, '0')}:00`);
    });

    chartSeries = computed<ChartSeries[]>(() => {
        const data = this.comparisonData();
        if (!data || !data.hourly_data || data.hourly_data.length === 0) return [];

        const series: ChartSeries[] = [];

        // 1. Фактична генерація (PVOutput)
        if (data.has_actual_data) {
            const actualValues = data.hourly_data.map(item => item.actual_kw);
            series.push({
                name: 'Фактична генерація (PVOutput, кВт)',
                data: actualValues,
                color: '#ea580c',
                fillColor: 'rgba(234, 88, 12, 0.10)'
            });
        }

        // 2. Прогнози для кожного активного джерела
        const activeSources = this.availableSourcesWithData();
        const sourceColorMap: Record<string, { color: string; fill: string }> = {
            'OpenWeatherMap': {color: '#2563eb', fill: 'rgba(37, 99, 235, 0.08)'},
            'Open-Meteo': {color: '#f59e0b', fill: 'rgba(245, 158, 11, 0.08)'},
            'Visual-Crossing': {color: '#10b981', fill: 'rgba(16, 185, 129, 0.08)'},
            'Open-Meteo-Archive': {color: '#8b5cf6', fill: 'rgba(139, 92, 246, 0.08)'}
        };

        for (const src of activeSources) {
            const values = data.hourly_data.map(item => {
                if (item.sources && item.sources[src]) {
                    return item.sources[src].forecast_kw;
                }
                if (src === data.weather_source) {
                    return item.forecast_kw;
                }
                return 0;
            });

            const col = sourceColorMap[src] || {color: '#6b7280', fill: 'rgba(107, 114, 128, 0.08)'};
            series.push({
                name: `${src} (Прогноз, кВт)`,
                data: values,
                color: col.color,
                fillColor: col.fill
            });
        }

        return series;
    });

    metricsList = computed<Array<{
        source: string;
        total_actual_kwh: number;
        total_forecast_kwh: number;
        total_delta_kwh: number;
        abs_error_kwh: number;
        relative_error_percent: number;
        mae_kw?: number;
        rmse_kw?: number;
    }>>(() => {
        const data = this.comparisonData();
        if (!data) return [];
        const activeSources = this.availableSourcesWithData();
        const sMetrics = data.sources_metrics || {};

        const list: Array<{
            source: string;
            total_actual_kwh: number;
            total_forecast_kwh: number;
            total_delta_kwh: number;
            abs_error_kwh: number;
            relative_error_percent: number;
            mae_kw?: number;
            rmse_kw?: number;
        }> = [];

        for (const src of activeSources) {
            const m = sMetrics[src] || (src === data.weather_source ? data.metrics : null);
            if (m) {
                list.push({
                    source: src,
                    ...m
                });
            }
        }

        return list;
    });

    ngOnInit(): void {
        this.loadStations();
    }

    loadStations(): void {
        this.loading.set(true);
        this.stationService.getStations().subscribe({
            next: (data) => {
                this.stations.set(data);
                if (data.length > 0) {
                    const stationId = data[0].id;
                    this.selectedStationId.set(stationId);
                    this.loadModels(stationId, (modelId) => {
                        this.loadAvailableDates(stationId, modelId);
                    });
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

    loadModels(stationId: number, onComplete?: (chosenModelId: number | null) => void): void {
        this.loadingModels.set(true);
        this.generationService.getNeuralModels(stationId).subscribe({
            next: (modelList) => {
                this.models.set(modelList);
                let targetModelId: number | null = null;
                if (modelList.length > 0) {
                    const currentSelected = this.selectedModelId();
                    const exists = modelList.some(m => m.id === currentSelected);
                    if (currentSelected && exists) {
                        targetModelId = currentSelected;
                    } else {
                        targetModelId = modelList[0].id;
                    }
                }
                this.selectedModelId.set(targetModelId);
                this.loadingModels.set(false);
                if (onComplete) {
                    onComplete(targetModelId);
                }
            },
            error: () => {
                this.models.set([]);
                this.selectedModelId.set(null);
                this.loadingModels.set(false);
                if (onComplete) {
                    onComplete(null);
                }
            }
        });
    }

    loadAvailableDates(stationId: number, modelId?: number | null): void {
        this.loading.set(true);
        const yesterdayDate = this.getDefaultDate();
        this.selectedDate.set(yesterdayDate);

        this.comparisonService.getAvailableDates(stationId).subscribe({
            next: (res) => {
                this.availableDates.set(res.dates);
                this.loadComparison(stationId, yesterdayDate, false, modelId);
            },
            error: () => {
                this.loadComparison(stationId, yesterdayDate, false, modelId);
            }
        });
    }

    onStationChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        const stationId = Number(select.value);
        this.loading.set(true);
        this.error.set(null);
        this.selectedStationId.set(stationId);
        this.loadModels(stationId, (modelId) => {
            this.loadAvailableDates(stationId, modelId);
        });
    }

    onModelChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        const modelId = Number(select.value);
        this.selectedModelId.set(modelId);
        this.loading.set(true);
        this.error.set(null);
        const stationId = this.selectedStationId();
        const dateStr = this.selectedDate();
        if (stationId && dateStr) {
            this.loadComparison(stationId, dateStr);
        }
    }

    onDateInputChange(event: Event): void {
        const input = event.target as HTMLInputElement;
        if (input.value) {
            this.selectedDate.set(input.value);
            if (this.isArchiveDisabled() && this.selectedSources().includes('Open-Meteo-Archive')) {
                this.selectedSources.set(this.selectedSources().filter(s => s !== 'Open-Meteo-Archive'));
            }
            this.loading.set(true);
            this.error.set(null);
            const stationId = this.selectedStationId();
            if (stationId) {
                this.loadComparison(stationId, input.value);
            }
        }
    }

    loadComparison(stationId: number, dateStr: string, forceSync: boolean = false, modelId?: number | null): void {
        this.loading.set(true);
        this.error.set(null);
        const effectiveModelId = (modelId !== undefined ? modelId : this.selectedModelId()) || undefined;

        this.comparisonService.getComparison(
            stationId,
            dateStr,
            'ALL',
            effectiveModelId,
            forceSync
        ).subscribe({
            next: (res) => {
                this.comparisonData.set(res);
                this.loading.set(false);
            },
            error: (err) => {
                this.comparisonData.set(null);
                this.error.set(err.error?.detail || 'Помилка отримання порівняння генерації');
                this.loading.set(false);
            }
        });
    }

    syncFromPVOutput(): void {
        const stationId = this.selectedStationId();
        const dateStr = this.selectedDate();
        if (!stationId || !dateStr) return;

        this.syncing.set(true);
        this.error.set(null);

        this.comparisonService.syncActual(stationId, dateStr).subscribe({
            next: () => {
                this.syncing.set(false);
                this.loadComparison(stationId, dateStr, false);
            },
            error: (err) => {
                this.syncing.set(false);
                this.error.set(err.error?.detail || 'Помилка синхронізації з PVOutput');
            }
        });
    }

    getSourceBadgeClass(source: string): string {
        switch (source) {
            case 'OpenWeatherMap':
                return 'badge-owm';
            case 'Open-Meteo':
                return 'badge-openmeteo';
            case 'Visual-Crossing':
                return 'badge-visualcrossing';
            case 'Open-Meteo-Archive':
                return 'badge-archive';
            default:
                return 'badge-default';
        }
    }

    getSourceHourly(row: HourlyComparisonItem, source: string): HourlySourceData | null {
        if (row.sources && row.sources[source]) {
            return row.sources[source];
        }
        if (this.comparisonData()?.weather_source === source) {
            return {
                forecast_watts: row.forecast_watts,
                forecast_kw: row.forecast_kw,
                delta_watts: row.delta_watts,
                delta_kw: row.delta_kw,
                abs_delta_kw: row.abs_delta_kw
            };
        }
        return null;
    }
}
