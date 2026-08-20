export interface ComparisonMetrics {
    total_actual_kwh: number;
    total_forecast_kwh: number;
    total_delta_kwh: number;
    abs_error_kwh: number;
    relative_error_percent: number;
    mae_kw?: number;
    rmse_kw?: number;
}

export interface HourlySourceData {
    forecast_watts: number;
    forecast_kw: number;
    delta_watts: number;
    delta_kw: number;
    abs_delta_kw: number;
}

export interface HourlyComparisonItem {
    hour: number;
    timestamp: string;
    actual_watts: number;
    actual_kw: number;
    st_s: number;
    forecast_watts: number;
    forecast_kw: number;
    delta_watts: number;
    delta_kw: number;
    abs_delta_kw: number;
    sources?: Record<string, HourlySourceData>;
}

export interface ComparisonResponse {
    station_id: number;
    station_name: string;
    date: string;
    weather_source: string;
    has_forecast_data: boolean;
    has_actual_data: boolean;
    available_sources?: string[];
    sources_metrics?: Record<string, ComparisonMetrics>;
    metrics: ComparisonMetrics;
    hourly_data: HourlyComparisonItem[];
    scientific_memo: string;
}

export interface ComparisonDatesResponse {
    station_id: number;
    count: number;
    dates: string[];
}
