import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-stat-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="bg-card-light rounded-2xl border border-gray-200 shadow-card p-5 flex justify-between items-start">
      <div>
        <p class="text-xs uppercase tracking-wide text-gray-500 mb-2">{{ title }}</p>
        <p class="text-3xl font-semibold text-text-light">{{ value }}</p>
        <p *ngIf="trend" class="text-xs text-green-600 mt-1">{{ trend }}</p>
      </div>
      <div class="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
        <span class="material-icons">{{ icon }}</span>
      </div>
    </div>
  `
})
export class StatCardComponent {
  @Input() title = '';
  @Input() value = '';
  @Input() icon = 'insights';
  @Input() trend?: string;
}
