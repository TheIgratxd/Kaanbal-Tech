import {
  Injectable,
  UnauthorizedException,
  BadRequestException,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ConflictException } from '@nestjs/common';

import { SupabaseService } from '../supabase/supabase.service';
import { RegisterDto } from './dto/register.dto';
import { LoginDto } from './dto/login.dto';

@Injectable()
export class AuthService {
  constructor(
    private readonly supabase: SupabaseService,
    private readonly config: ConfigService,
  ) {}

  async register(data: RegisterDto) {
    console.log('REGISTER recibido:', data.email);
    const frontendUrl =
      this.config.get<string>('FRONTEND_URL') ?? 'http://localhost:5173';

    const { data: result, error } =
      await this.supabase.getClient().auth.signUp({
        email: data.email,
        password: data.password,
        options: {
          emailRedirectTo: `${frontendUrl}/login`,
          data: {
            full_name: data.name,
          },
        },
      });

    if (error) {
      console.error('Supabase error:', error.message, (error as any).cause);
      if (error.status === HttpStatus.TOO_MANY_REQUESTS) {
        throw new HttpException(error.message, HttpStatus.TOO_MANY_REQUESTS);
      }
      throw new BadRequestException(error.message);
    }
    //Verificación del correo si está repetido
    if (result.user && result.user.identities?.length === 0) {
      throw new ConflictException('Este correo ya está registrado');
    }
    

    return {
      message: 'Registro realizado correctamente',
      user: result.user,
      session: result.session,
    };
  }

  async login(data: LoginDto) {
    const { data: result, error } =
      await this.supabase.getClient().auth.signInWithPassword({
        email: data.email,
        password: data.password,
      });

    if (error) {
      throw new UnauthorizedException(
        'Correo o contraseña incorrectos',
      );
    }

    return {
      message: 'Inicio de sesión correcto',
      user: result.user,
      session: result.session,
    };
  }
}