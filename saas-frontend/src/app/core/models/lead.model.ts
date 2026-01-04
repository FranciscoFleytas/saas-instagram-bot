export type LeadStatus = 'pending' | 'contacted';

export interface Lead {
  id: number;
  ig_username: string;
  full_name: string;
  status: LeadStatus;
  data: {
    followers: number;
    engagement: string;
    niche: string;
  };
}
