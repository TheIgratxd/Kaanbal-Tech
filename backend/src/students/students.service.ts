import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { User } from '@supabase/supabase-js';
import { randomUUID } from 'crypto';
import { SupabaseService } from '../supabase/supabase.service';
import { SubmitDiagnosticDto } from './dto/submit-diagnostic.dto';

export interface StudentRow {
  id: string;
  name: string;
  grade: string | null;
  año: string;
  email: string;
  created_at: string | null;
  student_id: number | null;
}

@Injectable()
export class StudentsService {
  constructor(private readonly supabaseService: SupabaseService) {}

  private get db() {
    return this.supabaseService.getClient();
  }

  private async ensureStudentRecord(user: User): Promise<StudentRow> {
    const { data: byId, error: byIdError } = await this.db
      .from('students')
      .select('*')
      .eq('id', user.id)
      .maybeSingle();

    if (byIdError) {
      throw new BadRequestException(
        `Error consultando students por id: ${byIdError.message}`,
      );
    }
    if (byId) {
      return byId as StudentRow;
    }

    if (user.email) {
      const { data: byEmail, error: byEmailError } = await this.db
        .from('students')
        .select('*')
        .eq('email', user.email)
        .maybeSingle();

      if (byEmailError) {
        throw new BadRequestException(
          `Error consultando students por email: ${byEmailError.message}`,
        );
      }
      if (byEmail) {
        return byEmail as StudentRow;
      }
    }

    const fallbackName =
      typeof user.user_metadata?.full_name === 'string' &&
      user.user_metadata.full_name.trim()
        ? user.user_metadata.full_name
        : user.email ?? 'Alumno';

    const { data: inserted, error: insertError } = await this.db
      .from('students')
      .insert({
        id: user.id,
        name: fallbackName,
        grade:
          typeof user.user_metadata?.academic_level === 'string'
            ? user.user_metadata.academic_level
            : 'Secundaria',
        año: String(new Date().getFullYear()),
        email: user.email ?? `${user.id}@sin-correo.local`,
      })
      .select('*')
      .single();

    if (insertError) {
      throw new BadRequestException(
        `Error creando registro en students: ${insertError.message}`,
      );
    }

    return inserted as StudentRow;
  }

  async getProfile(user: User) {
    const student = await this.ensureStudentRecord(user);

    let academicLevel: string | null =
      typeof user.user_metadata?.academic_level === 'string'
        ? user.user_metadata.academic_level
        : student.grade ?? null;

    if (student.student_id !== null && student.student_id !== undefined) {
      const { data: acad, error: acadError } = await this.db
        .from('academic_info')
        .select('educational_level, grade')
        .eq('student_id', student.student_id)
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle();

      if (acadError) {
        throw new BadRequestException(
          `Error consultando academic_info: ${acadError.message}`,
        );
      }
      if (acad?.educational_level) {
        academicLevel = acad.educational_level;
      }
    }

    const { count, error: countError } = await this.db
      .from('student_answers')
      .select('id', { count: 'exact', head: true })
      .eq('student_id', student.id);

    if (countError) {
      throw new BadRequestException(
        `Error verificando diagnóstico en student_answers: ${countError.message}`,
      );
    }

    return {
      id: user.id,
      name: student.name || user.user_metadata?.full_name || user.email,
      email: student.email || user.email,
      academic_level: academicLevel,
      diagnostic_done: (count ?? 0) > 0,
      created_at: student.created_at ?? user.created_at,
    };
  }

  async getDashboard(user: User) {
    const db = this.supabaseService.getClient();

    // 1. Datos base del usuario (priorizando tabla `users` y cayendo a auth user si no existe fila)
    const { data: userRow, error: userError } = await db
      .from('users')
      .select('*')
      .eq('id', user.id)
      .maybeSingle();

    if (userError) {
      throw new BadRequestException(
        `Error consultando la tabla users: ${userError.message}`,
      );
    }

    const userData = userRow ?? {
      id: user.id,
      email: user.email ?? null,
      name:
        typeof user.user_metadata?.full_name === 'string'
          ? user.user_metadata.full_name
          : user.email ?? 'Usuario',
    };

    // 2. Buscar registro en `students` si ya existe (sin forzar creación si aún no toma diagnóstico)
    let studentRecord: StudentRow | null = null;

    const { data: studentById, error: studentByIdError } = await db
      .from('students')
      .select('*')
      .eq('id', user.id)
      .maybeSingle();

    if (studentByIdError) {
      throw new BadRequestException(
        `Error consultando students: ${studentByIdError.message}`,
      );
    }

    if (studentById) {
      studentRecord = studentById as StudentRow;
    } else if (user.email) {
      const { data: studentByEmail, error: studentByEmailError } = await db
        .from('students')
        .select('*')
        .eq('email', user.email)
        .maybeSingle();

      if (studentByEmailError) {
        throw new BadRequestException(
          `Error consultando students por email: ${studentByEmailError.message}`,
        );
      }
      if (studentByEmail) {
        studentRecord = studentByEmail as StudentRow;
      }
    }

    const studentLookupId = studentRecord?.id ?? user.id;

    // 3. Consultar respuestas guardadas en `student_answers` para saber estado y último intento
    const { data: answers, error: answersError } = await db
      .from('student_answers')
      .select('attempt_id, question_id, is_correct, score, answered_at')
      .eq('student_id', studentLookupId)
      .order('answered_at', { ascending: false });

    if (answersError) {
      throw new BadRequestException(
        `Error consultando student_answers: ${answersError.message}`,
      );
    }

    // 4. Consultar habilidades iniciales en `student_skill`
    const { data: skills, error: skillsError } = await db
      .from('student_skill')
      .select('id, skill_id, mastery_score, confidence, last_evaluated_at')
      .eq('student_id', studentLookupId);

    if (skillsError) {
      throw new BadRequestException(
        `Error consultando student_skill: ${skillsError.message}`,
      );
    }

    // 5. Consolidar resumen del último intento de diagnóstico si existe
    const answerList = answers ?? [];
    const diagnosticDone = answerList.length > 0;
    let latestAttempt: {
      attempt_id: string | null;
      answered_at: string | null;
      correct_count: number;
      total_questions: number;
      score: number;
      percentage: number;
    } | null = null;

    if (diagnosticDone) {
      const latestAttemptId = answerList[0].attempt_id ?? null;
      const attemptAnswers = latestAttemptId
        ? answerList.filter((a) => a.attempt_id === latestAttemptId)
        : answerList;

      const totalQuestions = attemptAnswers.length;
      const correctCount = attemptAnswers.filter((a) => Boolean(a.is_correct)).length;
      const totalScore = attemptAnswers.reduce(
        (acc, item) => acc + Number(item.score ?? 0),
        0,
      );
      const percentage =
        totalQuestions > 0
          ? Number(((correctCount / totalQuestions) * 100).toFixed(2))
          : 0;

      latestAttempt = {
        attempt_id: latestAttemptId,
        answered_at: answerList[0].answered_at ?? null,
        correct_count: correctCount,
        total_questions: totalQuestions,
        score: totalScore,
        percentage,
      };
    }

    return {
      user: userData,
      diagnostic: {
        completed: diagnosticDone,
        total_answers: answerList.length,
        latest_attempt: latestAttempt,
        skills: skills ?? [],
      },
      student: studentRecord,
    };
  }

  async getDiagnosticQuestions(grade: number, limit = 5) {
    const { data: questions, error: qError } = await this.db
      .from('questions')
      .select('id, grade, question_type, question_text, max_score, order_index')
      .eq('grade', grade)
      .eq('is_active', true);

    if (qError) {
      throw new BadRequestException(
        `Error obteniendo preguntas: ${qError.message}`,
      );
    }

    if (!questions?.length) {
      return { grade, questions: [] };
    }

    // Mezcla aleatoria de preguntas restringidas al grado solicitado y toma hasta `limit`
    const shuffledQuestions = [...questions]
      .sort(() => Math.random() - 0.5)
      .slice(0, limit);

    const questionIds = shuffledQuestions.map((q) => q.id);

    const { data: options, error: optError } = await this.db
      .from('options')
      .select('id, question_id, option_text, order_index')
      .in('question_id', questionIds);

    if (optError) {
      throw new BadRequestException(
        `Error obteniendo opciones: ${optError.message}`,
      );
    }

    const optionsMap = new Map<
      string,
      Array<{ id: string; option_text: string; order_index: number }>
    >();

    for (const opt of options ?? []) {
      const current = optionsMap.get(opt.question_id) ?? [];
      current.push({
        id: opt.id,
        option_text: opt.option_text,
        order_index: opt.order_index,
      });
      optionsMap.set(opt.question_id, current);
    }

    return {
      grade,
      questions: shuffledQuestions.map((q) => ({
        ...q,
        options: (optionsMap.get(q.id) ?? []).sort(() => Math.random() - 0.5),
      })),
    };
  }

  async submitDiagnostic(user: User, dto: SubmitDiagnosticDto) {
    const student = await this.ensureStudentRecord(user);

    // 1. Verificar que no manden preguntas repetidas en el mismo intento
    const questionIds = dto.answers.map((a) => a.questionId);
    const uniqueQuestionIds = [...new Set(questionIds)];
    if (uniqueQuestionIds.length !== questionIds.length) {
      throw new BadRequestException(
        'Existen preguntas duplicadas en las respuestas enviadas',
      );
    }

    // 2. Consultar preguntas y sus opciones reales en BD
    const { data: questions, error: qError } = await this.db
      .from('questions')
      .select('id, question_type, correct_answer_text, max_score')
      .in('id', uniqueQuestionIds);

    if (qError) {
      throw new BadRequestException(
        `Error consultando preguntas: ${qError.message}`,
      );
    }

    const questionMap = new Map((questions ?? []).map((q) => [q.id, q]));

    const { data: options, error: optError } = await this.db
      .from('options')
      .select('id, question_id, is_correct')
      .in('question_id', uniqueQuestionIds);

    if (optError) {
      throw new BadRequestException(
        `Error consultando opciones: ${optError.message}`,
      );
    }

    const optionMap = new Map(
      (options ?? []).map((o) => [o.id, o]),
    );

    // 3. Evaluar cada respuesta en el backend
    const attemptId = randomUUID();
    let totalScore = 0;
    let maxScoreTotal = 0;
    let correctCount = 0;

    const answersToInsert = dto.answers.map((ans) => {
      const question = questionMap.get(ans.questionId);
      if (!question) {
        throw new NotFoundException(`Pregunta no encontrada: ${ans.questionId}`);
      }

      if (!ans.selectedOptionId && (!ans.rawAnswer || !ans.rawAnswer.trim())) {
        throw new BadRequestException(
          `La pregunta ${ans.questionId} no tiene respuesta seleccionada ni texto`,
        );
      }

      const maxScore = Number(question.max_score ?? 1);
      maxScoreTotal += maxScore;

      let isCorrect = false;

      if (ans.selectedOptionId) {
        const selectedOpt = optionMap.get(ans.selectedOptionId);
        if (!selectedOpt) {
          throw new BadRequestException(
            `La opción ${ans.selectedOptionId} no existe`,
          );
        }
        if (selectedOpt.question_id !== ans.questionId) {
          throw new BadRequestException(
            `La opción ${ans.selectedOptionId} no pertenece a la pregunta ${ans.questionId}`,
          );
        }
        isCorrect = Boolean(selectedOpt.is_correct);
      } else if (
        ans.rawAnswer !== undefined &&
        question.correct_answer_text !== null
      ) {
        isCorrect =
          ans.rawAnswer.trim().toLowerCase() ===
          String(question.correct_answer_text).trim().toLowerCase();
      }

      if (isCorrect) {
        correctCount += 1;
      }

      const score = isCorrect ? maxScore : 0;
      totalScore += score;

      return {
        attempt_id: attemptId,
        student_id: student.id,
        question_id: ans.questionId,
        selected_option_id: ans.selectedOptionId ?? null,
        raw_answer: ans.rawAnswer?.trim() ?? null,
        is_correct: isCorrect,
        score,
      };
    });

    // 4. Insertar respuestas en student_answers
    const { error: insertAnswersError } = await this.db
      .from('student_answers')
      .insert(answersToInsert);

    if (insertAnswersError) {
      throw new BadRequestException(
        `Error guardando respuestas en student_answers: ${insertAnswersError.message}`,
      );
    }

    // 5. Calcular nivel inicial y actualizar students / academic_info
    const percentage =
      maxScoreTotal > 0 ? (totalScore / maxScoreTotal) * 100 : 0;
    const masteryRatio =
      maxScoreTotal > 0 ? Number((totalScore / maxScoreTotal).toFixed(2)) : 0;

    const learningLevel =
      percentage >= 80
        ? 'Avanzado'
        : percentage >= 50
          ? 'Intermedio'
          : 'Básico';

    const normalizedLevel = dto.educationalLevel.trim().toUpperCase();

    const { error: updateStudentError } = await this.db
      .from('students')
      .update({
        grade: `${normalizedLevel} (${learningLevel})`,
      })
      .eq('id', student.id);

    if (updateStudentError) {
      throw new BadRequestException(
        `Error actualizando students: ${updateStudentError.message}`,
      );
    }

    if (student.student_id !== null && student.student_id !== undefined) {
      const { data: existingAcad, error: acadLookupError } = await this.db
        .from('academic_info')
        .select('id')
        .eq('student_id', student.student_id)
        .limit(1)
        .maybeSingle();

      if (acadLookupError) {
        throw new BadRequestException(
          `Error buscando academic_info: ${acadLookupError.message}`,
        );
      }

      if (existingAcad?.id) {
        const { error: acadUpdateError } = await this.db
          .from('academic_info')
          .update({
            educational_level: normalizedLevel,
            grade: dto.grade,
            ...(dto.schoolYear ? { school_year: dto.schoolYear } : {}),
          })
          .eq('id', existingAcad.id);

        if (acadUpdateError) {
          throw new BadRequestException(
            `Error actualizando academic_info: ${acadUpdateError.message}`,
          );
        }
      } else {
        const { error: acadInsertError } = await this.db
          .from('academic_info')
          .insert({
            student_id: student.student_id,
            educational_level: normalizedLevel,
            grade: dto.grade,
            school_year: dto.schoolYear ?? String(new Date().getFullYear()),
            enrollment_status: 'ACTIVE',
            created_at: new Date().toISOString(),
          });

        if (acadInsertError) {
          throw new BadRequestException(
            `Error insertando en academic_info: ${acadInsertError.message}`,
          );
        }
      }
    }

    // 6. Registrar/actualizar habilidad general inicial (skill_id = 1) en student_skill
    const nowIso = new Date().toISOString();
    const { data: existingSkill } = await this.db
      .from('student_skill')
      .select('id')
      .eq('student_id', student.id)
      .eq('skill_id', 1)
      .maybeSingle();

    if (existingSkill?.id) {
      await this.db
        .from('student_skill')
        .update({
          mastery_score: masteryRatio,
          confidence: Number(
            Math.min(1, dto.answers.length / 5).toFixed(2),
          ),
          last_evaluated_at: nowIso,
          updated_at: nowIso,
        })
        .eq('id', existingSkill.id);
    } else {
      await this.db.from('student_skill').insert({
        student_id: student.id,
        skill_id: 1,
        mastery_score: masteryRatio,
        confidence: Number(Math.min(1, dto.answers.length / 5).toFixed(2)),
        last_evaluated_at: nowIso,
        created_at: nowIso,
        updated_at: nowIso,
      });
    }

    const updatedProfile = await this.getProfile(user);

    return {
      profile: updatedProfile,
      attempt_id: attemptId,
      correct_count: correctCount,
      total_questions: dto.answers.length,
      score: totalScore,
      max_score: maxScoreTotal,
      percentage: Number(percentage.toFixed(2)),
      learning_level: learningLevel,
      mastery_score: masteryRatio,
    };
  }
}