import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module';
import { SupabaseModule } from '../supabase/supabase.module';
import { UsersController } from './users.controller';

@Module({
  imports: [SupabaseModule, AuthModule],
  controllers: [UsersController],
})
export class UsersModule {}