import { Controller, Get, Req, UseGuards } from '@nestjs/common';
import { User } from '@supabase/supabase-js';
import { Request } from 'express';
import { SupabaseAuthGuard } from '../auth/supabase-auth.guard';

@Controller('users')
@UseGuards(SupabaseAuthGuard)
export class UsersController {
  @Get('me')
  getMe(@Req() req: Request & { user: User }) {
    const authUser = req.user;

    return {
      id: authUser.id,
      email: authUser.email ?? null,
      name:
        typeof authUser.user_metadata?.full_name === 'string'
          ? authUser.user_metadata.full_name
          : typeof authUser.user_metadata?.name === 'string'
            ? authUser.user_metadata.name
            : authUser.email ?? 'Usuario',
      metadata: authUser.user_metadata ?? {},
      created_at: authUser.created_at ?? null,
    };
  }
}