import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { delay, Observable, of } from 'rxjs';
import { Lead } from '../models/lead.model';

@Injectable({
  providedIn: 'root'
})
export class LeadService {
  private readonly http = inject(HttpClient);

  getLeads(): Observable<Lead[]> {
    const mockLeads: Lead[] = [
      {
        id: 1,
        ig_username: 'tech_guru',
        full_name: 'Tech Guru',
        status: 'pending',
        data: { followers: 12500, engagement: '4.2%', niche: 'Tech' }
      },
      {
        id: 2,
        ig_username: 'startup_daily',
        full_name: 'Startup Daily',
        status: 'contacted',
        data: { followers: 18900, engagement: '3.6%', niche: 'Business' }
      },
      {
        id: 3,
        ig_username: 'design_muse',
        full_name: 'Design Muse',
        status: 'pending',
        data: { followers: 9800, engagement: '5.1%', niche: 'Design' }
      },
      {
        id: 4,
        ig_username: 'fitness_journey',
        full_name: 'Fitness Journey',
        status: 'contacted',
        data: { followers: 22100, engagement: '4.8%', niche: 'Health' }
      }
    ];

    return of(mockLeads).pipe(delay(300));
  }
}
