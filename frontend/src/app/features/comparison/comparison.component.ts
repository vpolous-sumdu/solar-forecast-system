import {Component, computed, inject, OnInit, signal} from '@angular/core';
import {CommonModule, DecimalPipe} from '@angular/common';
import {StationService} from '../../core/services/station.service';
import {ComparisonService} from '../../core/services/comparison.service';
import {GenerationService} from '../../core/services/generation.service';
import {Station} from '../../core/models/station.model';
import {ComparisonResponse} from '../../core/models/comparison.model';
import {ChartSeries} from '../../core/models/chart.model';
import {NeuralModel} from '../../core/models/neural-model.model';
import {PowerChartComponent} from '../../shared/components/power-chart/power-chart.component';

@Component({
    selector: 'app-comparison',
    standalone: true,
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
    selectedWeatherSource = signal<string>('OpenWeatherMap');
    models = signal<NeuralModel[]>([]);
    selectedModelId = signal<number | null>(null);
    loadingModels = signal<boolean>(false);

    comparisonData = signal<ComparisonResponse | null>(null);
    loading = signal<boolean>(false);
    syncing = signal<boolean>(false);
    error = signal<string | null>(null);

    private getDefaultDate(): string {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        return yesterday.toISOString().split('T')[0];
    }

    chartLabels = computed<string[]>(() => {
        const data = this.comparisonData();
        if (!data || !data.hourly_data || data.hourly_data.length === 0) return [];
        return data.hourly_data.map(item => `${String(item.hour).padStart(2, '0')}:00`);
    });

    chartSeries = computed<ChartSeries[]>(() => {
        const data = this.comparisonData();
        if (!data || !data.hourly_data || data.hourly_data.length === 0) return [];

        const forecastValues = data.hourly_data.map(item => item.forecast_kw);
        const actualValues = data.hourly_data.map(item => item.actual_kw);

        return [
            {
                name: 'Прогноз генерації (кВт)',
                data: forecastValues,
                color: '#2563eb',
                fillColor: 'rgba(37, 99, 235, 0.12)'
            },
            {
                name: 'Фактична генерація (PVOutput, кВт)',
                data: actualValues,
                color: '#f97316',
                fillColor: 'rgba(249, 115, 22, 0.10)'
            }
        ];
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
                    this.selectedStationId.set(data[0].id);
                    this.loadModels(data[0].id);
                    this.loadAvailableDates(data[0].id);
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

    loadAvailableDates(stationId: number): void {
        this.loading.set(true);
        const yesterdayDate = this.getDefaultDate(); // Завжди попередній день (вчора)
        this.selectedDate.set(yesterdayDate);

        this.comparisonService.getAvailableDates(stationId).subscribe({
            next: (res) => {
                this.availableDates.set(res.dates);
                // Завантажуємо порівняння строго на попередній день
                this.loadComparison(stationId, yesterdayDate);
            },
            error: () => {
                this.loadComparison(stationId, yesterdayDate);
            }
        });
    }



    onStationChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        const stationId = Number(select.value);
        this.loading.set(true);
        this.error.set(null);
        this.selectedStationId.set(stationId);
        this.loadModels(stationId);
        this.loadAvailableDates(stationId);
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

    onDateSelectChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        this.selectedDate.set(select.value);
        this.loading.set(true);
        this.error.set(null);
        const stationId = this.selectedStationId();
        if (stationId && select.value) {
            this.loadComparison(stationId, select.value);
        }
    }

    onDateInputChange(event: Event): void {
        const input = event.target as HTMLInputElement;
        if (input.value) {
            this.selectedDate.set(input.value);
            this.loading.set(true);
            this.error.set(null);
            const stationId = this.selectedStationId();
            if (stationId) {
                this.loadComparison(stationId, input.value);
            }
        }
    }

    onWeatherSourceChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        this.selectedWeatherSource.set(select.value);
        this.loading.set(true);
        this.error.set(null);
        const stationId = this.selectedStationId();
        const dateStr = this.selectedDate();
        if (stationId && dateStr) {
            this.loadComparison(stationId, dateStr);
        }
    }

    loadComparison(stationId: number, dateStr: string, forceSync: boolean = false): void {
        this.loading.set(true);
        this.error.set(null);

        this.comparisonService.getComparison(
            stationId,
            dateStr,
            this.selectedWeatherSource(),
            this.selectedModelId() || undefined,
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
                this.comparisonData.set(null);
                this.syncing.set(false);
                this.error.set(err.error?.detail || 'Помилка синхронізації з PVOutput');
            }
        });
    }
}
