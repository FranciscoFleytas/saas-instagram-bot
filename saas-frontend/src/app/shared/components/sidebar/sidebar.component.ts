import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <aside class="w-72 bg-card-light border-r border-gray-200 shadow-sm min-h-screen p-6 flex flex-col">
      <div class="flex items-center gap-2 mb-10">
        <div class="h-10 w-10 rounded-xl bg-primary text-white flex items-center justify-center font-bold shadow-card">
          SB
        </div>
        <div>
          <p class="text-lg font-semibold text-text-light leading-tight">SaaSBot</p>
          <p class="text-xs text-gray-500">Automation Suite</p>
        </div>
      </div>

      <nav class="space-y-1 flex-1">
        <a
          routerLink="/"
          routerLinkActive="bg-primary/10 text-primary"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
          [routerLinkActiveOptions]="{ exact: true }"
        >
          <span class="material-icons text-base">dashboard</span>
          Dashboard
        </a>
        <a
          routerLink="/bot-control"
          routerLinkActive="bg-primary/10 text-primary"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
        >
          <span class="material-icons text-base">smart_toy</span>
          Bot Control
        </a>
        <a
          routerLink="/leads"
          routerLinkActive="bg-primary/10 text-primary"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
        >
          <span class="material-icons text-base">people_alt</span>
          Leads Database
        </a>
      </nav>

      <div class="mt-10 bg-primary/10 border border-primary/20 rounded-xl p-4 text-sm text-gray-700">
        <p class="font-semibold text-text-light mb-1">Sistema Online</p>
        <p class="text-gray-500 text-xs">Worker y API operativos.</p>
      </div>
    </aside>
  `
})
export class SidebarComponent {}
