import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/stations/station-list.component').then(m => m.StationListComponent)
  },
  {
    path: 'forecast',
    loadComponent: () => import('./features/weather/weather-forecast.component').then(m => m.WeatherForecastComponent)
  },
  {
    path: '**',
    redirectTo: ''
  }
];
