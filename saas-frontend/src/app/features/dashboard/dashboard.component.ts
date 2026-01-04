import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core'; // 1. Importar inject
import { LeadService } from '../../core/services/lead.service';
import { StatCardComponent } from '../../shared/components/stat-card/stat-card.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, StatCardComponent],
  template: `
    <div class="space-y-8">
      <div class="flex items-start justify-between">
        <div>
          <h1 class="text-3xl font-bold text-text-light mb-1">Dashboard</h1>
          <p class="text-gray-500">Estado general de bots y campañas</p>
        </div>
        <span class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-100 text-green-700 text-sm font-medium">
          <span class="material-icons text-base">check_circle</span>
          Sistema Online
        </span>
      </div>

      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <app-stat-card title="Total Leads" value="12,450" icon="group" trend="+8.2% vs last week" />
        <app-stat-card title="Emails" value="8,932" icon="email" trend="+3.4% verified" />
        <app-stat-card title="Phones" value="4,021" icon="call" trend="+1.1% new" />
        <app-stat-card title="New Today" value="+145" icon="auto_graph" trend="steady growth" />
      </div>

      <div class="grid gap-6 md:grid-cols-2">
        <div class="bg-card-light rounded-2xl border border-gray-200 shadow-card p-6 space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-lg font-semibold text-text-light">Audience Extraction</h2>
              <p class="text-sm text-gray-500">Define la fuente y volumen de leads.</p>
            </div>
            <span class="material-icons text-primary">travel_explore</span>
          </div>
          <label class="text-sm font-medium text-gray-600">Target Source</label>
          <input type="text" placeholder="@example_account" class="w-full rounded-lg border border-gray-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/50" />
          <label class="text-sm font-medium text-gray-600">Volume</label>
          <input type="number" placeholder="500" class="w-full rounded-lg border border-gray-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/50" />
          <button class="w-full bg-primary text-white font-semibold rounded-lg py-3 hover:bg-blue-600 transition">Start Extraction</button>
        </div>

        <div class="bg-card-light rounded-2xl border border-gray-200 shadow-card p-6 space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-lg font-semibold text-text-light">Bot Control</h2>
              <p class="text-sm text-gray-500">Configura acciones automáticas.</p>
            </div>
            <span class="material-icons text-primary">smart_toy</span>
          </div>
          <label class="text-sm font-medium text-gray-600">Post URL</label>
          <input type="url" placeholder="https://instagram.com/p/..." class="w-full rounded-lg border border-gray-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/50" />
          <div class="grid grid-cols-2 gap-3">
            <label class="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" class="rounded border-gray-300 text-primary focus:ring-primary" /> Like
            </label>
            <label class="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" class="rounded border-gray-300 text-primary focus:ring-primary" /> Comment
            </label>
          </div>
          <label class="text-sm font-medium text-gray-600">AI Personality</label>
          <select class="w-full rounded-lg border border-gray-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/50">
            <option>Profesional</option>
            <option>Friendly</option>
            <option>Humor</option>
            <option>Sales</option>
          </select>
          <button class="w-full bg-primary text-white font-semibold rounded-lg py-3 hover:bg-blue-600 transition">Launch Campaign</button>
        </div>
      </div>

      <div class="bg-card-light rounded-2xl border border-gray-200 shadow-card">
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h3 class="text-lg font-semibold text-text-light">Lead Database</h3>
            <p class="text-sm text-gray-500">Resumen rápido de leads y estado.</p>
          </div>
          <button class="inline-flex items-center gap-2 text-sm font-medium text-primary bg-primary/10 px-4 py-2 rounded-lg">
            <span class="material-icons text-base">refresh</span>
            Sync
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th class="px-6 py-3 text-left">User</th>
                <th class="px-6 py-3 text-left">Metrics</th>
                <th class="px-6 py-3 text-left">Niche</th>
                <th class="px-6 py-3 text-left">Status</th>
                <th class="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100" *ngIf="leads$ | async as leads">
              <tr *ngFor="let lead of leads" class="hover:bg-gray-50">
                <td class="px-6 py-4">
                  <div class="flex items-center gap-3">
                    <div class="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-semibold">
                      {{ lead.ig_username.slice(0, 2).toUpperCase() }}
                    </div>
                    <div>
                      <p class="font-semibold text-text-light">@{{ lead.ig_username }}</p>
                      <p class="text-gray-500 text-xs">{{ lead.full_name }}</p>
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4 text-gray-700">
                  <div class="flex items-center gap-4">
                    <span class="flex items-center gap-1"><span class="material-icons text-base text-gray-400">group</span>{{ lead.data.followers | number }} </span>
                    <span class="flex items-center gap-1"><span class="material-icons text-base text-gray-400">trending_up</span>{{ lead.data.engagement }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 text-gray-700">{{ lead.data.niche }}</td>
                <td class="px-6 py-4">
                  <span
                    class="px-3 py-1 rounded-full text-xs font-semibold"
                    [ngClass]="{
                      'bg-green-100 text-green-700': lead.status === 'contacted',
                      'bg-yellow-100 text-yellow-700': lead.status === 'pending'
                    }"
                  >
                    {{ lead.status | titlecase }}
                  </span>
                </td>
                <td class="px-6 py-4 text-right">
                  <button class="text-primary hover:text-blue-700 inline-flex items-center gap-1 text-sm font-medium">
                    <span class="material-icons text-base">send</span>
                    DM
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `
})
export class DashboardComponent {
  // 2. Usar inject() en lugar del constructor
  private leadService = inject(LeadService);
  protected readonly leads$ = this.leadService.getLeads();

  // 3. Constructor vacío o eliminado
  constructor() {}
}