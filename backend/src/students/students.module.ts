import { Module } from '@nestjs/common';
import { SupabaseService } from '../supabase/supabase.service';
import { StudentsController } from './students.controller';
import { StudentsService } from './students.service';

@Module({
  controllers: [StudentsController],
  providers: [StudentsService, SupabaseService],
})
export class StudentsModule {}