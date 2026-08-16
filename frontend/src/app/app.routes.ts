import {Routes} from '@angular/router';
import {StationListComponent} from './features/stations/station-list.component';
import {WeatherForecastComponent} from './features/weather/weather-forecast.component';
import {ComparisonComponent} from './features/comparison/comparison.component';

export const routes: Routes = [
    {path: '', component: StationListComponent},
    {path: 'forecast', component: WeatherForecastComponent},
    {path: 'comparison', component: ComparisonComponent},
    {path: '**', redirectTo: ''}
];
