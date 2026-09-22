import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { RESPONSE_MESSAGE_KEY } from '../decorators/response-message.decorator';
import { SKIP_TRANSFORM_KEY } from '../decorators/skip-transform.decorator';

export interface ApiResponse<T> {
  success: boolean;
  statusCode: number;
  message: string;
  data: T;
  timestamp: string;
}

@Injectable()
export class TransformResponseInterceptor<T>
  implements NestInterceptor<T, ApiResponse<T> | T>
{
  constructor(private reflector: Reflector) {}

  intercept(
    context: ExecutionContext,
    next: CallHandler,
  ): Observable<ApiResponse<T> | T> {
    const skipTransform = this.reflector.getAllAndOverride<boolean>(
      SKIP_TRANSFORM_KEY,
      [context.getHandler(), context.getClass()],
    );

    if (skipTransform) {
      return next.handle();
    }

    const message =
      this.reflector.getAllAndOverride<string>(RESPONSE_MESSAGE_KEY, [
        context.getHandler(),
        context.getClass(),
      ]) || 'Thao tác thành công';

    const ctx = context.switchToHttp();
    const response = ctx.getResponse();
    const statusCode = response.statusCode || 200;

    return next.handle().pipe(
      map((data) => ({
        success: true,
        statusCode,
        message,
        data,
        timestamp: new Date().toISOString(),
      })),
    );
  }
}
