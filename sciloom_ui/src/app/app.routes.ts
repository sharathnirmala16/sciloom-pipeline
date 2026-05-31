import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full'
  },
  {
    path: 'dashboard',
    loadComponent: () => import('./components/dashboard/dashboard.component').then(m => m.DashboardComponent)
  },
  {
    path: 'job/:id',
    loadComponent: () => import('./components/job-details/job-details.component').then(m => m.JobDetailsComponent)
  },
  {
    path: '**',
    redirectTo: 'dashboard'
  }
];
