import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createClient, SupabaseClient } from '@supabase/supabase-js';

@Injectable()
export class SupabaseService {
  private readonly client: SupabaseClient;

  constructor(private readonly config: ConfigService) {
    const url = this.config.get<string>('SUPABASE_URL');
    const key =
      this.config.get<string>('SUPABASE_SERVICE_ROLE_KEY') ??
      this.config.get<string>('SUPABASE_SECRET_KEY');

    if (!url || !key) {
      throw new Error(
        `Supabase mal configurado. URL: ${Boolean(url)}, KEY: ${Boolean(key)}. Revisa el .env`,
      );
    }

    console.log('URL usada:', JSON.stringify(url));
    console.log('KEY largo:', key?.length);
    this.client = createClient(url, key);
  }

  getClient(): SupabaseClient {
    return this.client;
  }
}