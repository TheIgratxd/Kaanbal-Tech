import { User } from '@supabase/supabase-js';
import {
  BadRequestException,
  Body,
  Controller,
  Get,
  Post,
  Query,
  Req,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { SupabaseAuthGuard } from '../auth/supabase-auth.guard';
import { SubmitDiagnosticDto } from './dto/submit-diagnostic.dto';
import { StudentsService } from './students.service';

@Controller('students')
@UseGuards(SupabaseAuthGuard)
export class StudentsController {
  constructor(private readonly studentsService: StudentsService) {}

  @Get('dashboard')
  getDashboard(@Req() req: Request & { user: User }) {
    return this.studentsService.getDashboard(req.user);
  }

  @Get('diagnostic/questions')
  getDiagnosticQuestions(@Query('grade') gradeParam?: string) {
    const grade = Number(gradeParam);
    if (!gradeParam || Number.isNaN(grade) || grade < 1) {
      throw new BadRequestException(
        'El parámetro query "grade" debe ser un número entero válido',
      );
    }
    return this.studentsService.getDiagnosticQuestions(grade);
  }

  @Post('diagnostic')
  submitDiagnostic(
    @Req() req: Request & { user: User },
    @Body() dto: SubmitDiagnosticDto,
  ) {
    return this.studentsService.submitDiagnostic(req.user, dto);
  }
}