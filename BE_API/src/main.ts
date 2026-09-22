import { NestFactory, Reflector } from '@nestjs/core';
import {
  FastifyAdapter,
  NestFastifyApplication,
} from '@nestjs/platform-fastify';
import { ValidationPipe, Logger } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { AppModule } from './app.module';
import { TransformResponseInterceptor } from './common/interceptors/transform-response.interceptor';
import { AllExceptionsFilter } from './common/filters/all-exceptions.filter';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';

async function bootstrap() {
  const logger = new Logger('Bootstrap');

  const fastifyAdapter = new FastifyAdapter({
    logger: false,
  });

  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    fastifyAdapter,
  );

  // Security & Middlewares
  await app.register(helmet, {
    contentSecurityPolicy: false,
  });

  await app.register(cors, {
    origin: true,
    credentials: true,
  });

  // Global Pipelines
  const reflector = app.get(Reflector);
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: false,
    }),
  );

  app.useGlobalInterceptors(new TransformResponseInterceptor(reflector));
  app.useGlobalFilters(new AllExceptionsFilter());

  // Global Prefix
  const apiPrefix = process.env.API_PREFIX || 'api';
  app.setGlobalPrefix(apiPrefix);

  // Swagger Documentation Setup
  const config = new DocumentBuilder()
    .setTitle('Location-Based Decision Support System (L-DSS) API')
    .setDescription(
      'Hệ thống Hỗ trợ Ra Quyết định Địa điểm (Đà Nẵng) sử dụng phương pháp đa tiêu chí AHP + TOPSIS kết hợp tính toán không gian Haversine.',
    )
    .setVersion('1.0.0')
    .addTag('Recommendations (Đề xuất địa điểm L-DSS)', 'Đánh giá, xếp hạng và so sánh thực nghiệm')
    .addTag('DSS Engine (Thuật toán AHP & TOPSIS)', 'Xử lý ma trận so sánh cặp, kiểm định CR, chuẩn hóa trọng số')
    .addTag('Places (Địa điểm tại Đà Nẵng)', 'Quản lý và tìm kiếm địa điểm cafe, nhà hàng, khách sạn...')
    .addTag('Categories (Danh mục địa điểm)', 'Phân loại các loại địa điểm')
    .addTag('Seed Data & Crawl (Dữ liệu Đà Nẵng)', 'Khởi tạo dữ liệu thực tế và crawl bản đồ')
    .addTag('Users (Người dùng & Tùy chọn vị trí)', 'Quản lý thông tin và tọa độ mặc định')
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup(`${apiPrefix}/docs`, app, document, {
    swaggerOptions: {
      persistAuthorization: true,
      docExpansion: 'list',
      filter: true,
    },
  });

  const port = Number(process.env.PORT || 4000);
  await app.listen(port, '0.0.0.0');

  logger.log(`🚀 DSS API Server is running on: http://localhost:${port}/${apiPrefix}`);
  logger.log(`📖 Swagger API Documentation: http://localhost:${port}/${apiPrefix}/docs`);
}

bootstrap();
