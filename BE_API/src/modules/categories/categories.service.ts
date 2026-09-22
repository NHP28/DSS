import { Injectable, NotFoundException } from '@nestjs/common';
import { DrizzleService } from '../../drizzle/drizzle.service';
import { categories, Category, NewCategory } from '../../drizzle/schemas/categories.schema';
import { eq } from 'drizzle-orm';
import { CreateCategoryDto } from './dto/create-category.dto';

@Injectable()
export class CategoriesService {
  constructor(private readonly drizzle: DrizzleService) {}

  async findAll(): Promise<Category[]> {
    return this.drizzle.select().from(categories);
  }

  async findById(id: number): Promise<Category> {
    const result = await this.drizzle
      .select()
      .from(categories)
      .where(eq(categories.id, id))
      .limit(1);

    if (!result || result.length === 0) {
      throw new NotFoundException(`Không tìm thấy danh mục với id ${id}`);
    }
    return result[0];
  }

  async findBySlug(slug: string): Promise<Category | null> {
    const result = await this.drizzle
      .select()
      .from(categories)
      .where(eq(categories.slug, slug))
      .limit(1);

    return result[0] || null;
  }

  async create(dto: CreateCategoryDto): Promise<Category> {
    const insertData: NewCategory = {
      name: dto.name,
      slug: dto.slug,
      description: dto.description || null,
      icon: dto.icon || null,
    };

    const res = await this.drizzle.insert(categories).values(insertData);
    const insertId = (res[0] as any).insertId;
    return this.findById(insertId);
  }
}
