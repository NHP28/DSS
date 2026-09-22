import { Injectable, NotFoundException } from '@nestjs/common';
import { DrizzleService } from '../../drizzle/drizzle.service';
import { users, User, NewUser } from '../../drizzle/schemas/users.schema';
import { eq } from 'drizzle-orm';
import { CreateUserDto } from './dto/create-user.dto';

@Injectable()
export class UsersService {
  constructor(private readonly drizzle: DrizzleService) {}

  async findAll(): Promise<User[]> {
    return this.drizzle.select().from(users);
  }

  async findById(id: number): Promise<User> {
    const result = await this.drizzle
      .select()
      .from(users)
      .where(eq(users.id, id))
      .limit(1);

    if (!result || result.length === 0) {
      throw new NotFoundException(`Không tìm thấy người dùng với ID ${id}`);
    }
    return result[0];
  }

  async create(dto: CreateUserDto): Promise<User> {
    const insertData: NewUser = {
      name: dto.name,
      email: dto.email,
      defaultLatitude: dto.defaultLatitude ? String(dto.defaultLatitude) : '16.0614000',
      defaultLongitude: dto.defaultLongitude ? String(dto.defaultLongitude) : '108.2208000',
    };

    const res = await this.drizzle.insert(users).values(insertData);
    const insertId = (res[0] as any).insertId;
    return this.findById(insertId);
  }
}
