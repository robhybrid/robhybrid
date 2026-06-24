import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module.ts';

if (import.meta.env.PROD) {
  async function bootstrap() {
    const app = await NestFactory.create(AppModule);
    await app.listen(import.meta.env.PORT || 3000);
  }
  bootstrap();
}

export const viteNodeApp = NestFactory.create(AppModule);
