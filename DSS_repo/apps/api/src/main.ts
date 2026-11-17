import 'reflect-metadata';
import 'dotenv/config';
import { NestFactory } from '@nestjs/core';
import { FastifyAdapter, NestFastifyApplication } from '@nestjs/platform-fastify';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create<NestFastifyApplication>(AppModule,new FastifyAdapter());
  app.setGlobalPrefix('api');
  app.enableCors({origin:(process.env.WEB_ORIGIN || 'http://localhost:3000,http://127.0.0.1:3000').split(',')});
  app.useGlobalPipes(new ValidationPipe({transform:true,whitelist:true,forbidNonWhitelisted:true}));
  app.enableShutdownHooks();
  await app.listen(Number(process.env.PORT || 4000),process.env.HOST || '127.0.0.1');
}
bootstrap().catch(error=>{ console.error(error);process.exitCode=1; });
