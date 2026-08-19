import {
    Component,
    ElementRef,
    viewChild,
    input,
    effect,
    OnDestroy,
    afterNextRender,
    ChangeDetectionStrategy
} from '@angular/core';
import {Chart, registerables} from 'chart.js';
import {ChartSeries} from '../../../core/models/chart.model';

Chart.register(...registerables);

export type {ChartSeries};

@Component({
    selector: 'app-power-chart',
    standalone: true,
    changeDetection: ChangeDetectionStrategy.OnPush,
    templateUrl: './power-chart.component.html',
    styleUrl: './power-chart.component.css'
})
export class PowerChartComponent implements OnDestroy {
    canvasRef = viewChild<ElementRef<HTMLCanvasElement>>('chartCanvas');

    labels = input.required<string[]>();
    series = input.required<ChartSeries[]>();
    title = input<string>('Графік прогнозу потужності генерації СЕС (кВт)');
    loading = input<boolean>(false);

    private chart: Chart | null = null;
    private isRendered = false;

    constructor() {
        afterNextRender(() => {
            this.isRendered = true;
            if (!this.loading()) {
                this.updateChart();
            }
        });

        effect(() => {
            const lbls = this.labels();
            const srs = this.series();
            const isLoading = this.loading();
            if (this.isRendered && !isLoading) {
                setTimeout(() => this.updateChart(), 0);
            }
        });
    }

    ngOnDestroy(): void {
        this.destroyChart();
    }

    private destroyChart(): void {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    private updateChart(): void {
        const canvas = this.canvasRef()?.nativeElement;
        if (!canvas) return;

        const lbls = this.labels();
        const srs = this.series();
        if (!lbls || lbls.length === 0 || !srs || srs.length === 0) {
            this.destroyChart();
            return;
        }

        const datasets = srs.map(s => ({
            label: s.name,
            data: s.data,
            borderColor: s.color,
            backgroundColor: s.fillColor || 'transparent',
            borderWidth: 3,
            fill: !!s.fillColor,
            tension: 0.4,
            pointBackgroundColor: s.color,
            pointRadius: 4,
            pointHoverRadius: 6
        }));

        if (this.chart) {
            this.chart.data.labels = lbls;
            this.chart.data.datasets = datasets;
            this.chart.update('none');
            return;
        }

        this.chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: lbls,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {font: {family: 'Inter, system-ui, sans-serif', size: 12, weight: 600}}
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} кВт`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {display: false},
                        ticks: {font: {family: 'Inter, system-ui, sans-serif', size: 11}}
                    },
                    y: {
                        beginAtZero: true,
                        title: {display: true, text: 'Потужність (кВт)', font: {size: 12, weight: 600}},
                        ticks: {font: {family: 'Inter, system-ui, sans-serif', size: 11}}
                    }
                }
            }
        });
    }
}

