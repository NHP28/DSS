import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { DrizzleModule } from './drizzle/drizzle.module';
import { CategoriesModule } from './modules/categories/categories.module';
import { PlacesModule } from './modules/places/places.module';
import { DssModule } from './modules/dss/dss.module';
import { RecommendationModule } from './modules/recommendation/recommendation.module';
import { SeedModule } from './modules/seed/seed.module';
import { UsersModule } from './modules/users/users.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),
    DrizzleModule,
    CategoriesModule,
    PlacesModule,
    DssModule,
    RecommendationModule,
    SeedModule,
    UsersModule,
  ],
})
export class AppModule {}
