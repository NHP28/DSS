import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { AuthController } from './auth/auth.controller';
import { AuthService } from './auth/auth.service';
import { DatabaseService } from './database/database.service';
import { GoogleController } from './google/google.controller';
import { GoogleService } from './google/google.service';
import { KgController } from './kg/kg.controller';
import { createDriver, KgService, NEO4J_DRIVER } from './kg/kg.service';
import { RecommendService } from './recommend.service';
import { SettingsController } from './settings/settings.controller';
import { Store } from './store';
import { MemoryStore } from './store.memory';

export const controllers = [AppController, AuthController, SettingsController, KgController, GoogleController];
export const services = [AppService, AuthService, RecommendService, KgService, GoogleService];

@Module({
  controllers,
  providers: [...services, DatabaseService, { provide: NEO4J_DRIVER, useFactory: createDriver },
    // STORE=memory runs the API straight from the CSV files, without MySQL.
    { provide: Store, inject: [DatabaseService], useFactory: (db: DatabaseService) => process.env.STORE === 'memory' ? new MemoryStore() : new Store(db) }],
})
export class AppModule {}
