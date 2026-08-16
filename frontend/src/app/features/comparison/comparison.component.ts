import {Component, computed, inject, OnInit, signal} from '@angular/core';
import {CommonModule, DecimalPipe} from '@angular/common';
import {StationService} from '../../core/services/station.service';
import {ComparisonService} from '../../core/services/comparison.service';
import {Station} from '../../core/models/station.model';
import {ComparisonResponse} from '../../core/models/comparison.model';
import {ChartSeries} from '../../core/models/chart.model';
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

    stations = signal<Station[]>([]);
    selectedStationId = signal<number | null>(null);
    selectedDate = signal<string>('');
    availableDates = signal<string[]>([]);
    selectedWeatherSource = signal<string>('OpenWeatherMap');
    selectedModel = signal<string>('baseline');

    comparisonData = signal<ComparisonResponse | null>(null);
    loading = signal<boolean>(false);
    syncing = signal<boolean>(false);
    error = signal<string | null>(null);

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

    loadAvailableDates(stationId: number): void {
        this.loading.set(true);
        this.comparisonService.getAvailableDates(stationId).subscribe({
            next: (res) => {
                this.availableDates.set(res.dates);
                const currentDate = this.selectedDate();
                if (currentDate && res.dates.includes(currentDate)) {
                    this.loadComparison(stationId, currentDate);
                } else if (res.dates.length > 0) {
                    this.selectedDate.set(res.dates[0]);
                    this.loadComparison(stationId, res.dates[0]);
                } else {
                    const dateToUse = currentDate || new Date().toISOString().split('T')[0];
                    this.selectedDate.set(dateToUse);
                    this.loadComparison(stationId, dateToUse);
                }
            },
            error: () => {
                const dateToUse = this.selectedDate() || new Date().toISOString().split('T')[0];
                this.selectedDate.set(dateToUse);
                this.loadComparison(stationId, dateToUse);
            }
        });
    }

    onStationChange(event: Event): void {
        const select = event.target as HTMLSelectElement;
        const stationId = Number(select.value);
        this.loading.set(true);
        this.error.set(null);
        this.selectedStationId.set(stationId);
        this.loadAvailableDates(stationId);
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
            undefined,
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
