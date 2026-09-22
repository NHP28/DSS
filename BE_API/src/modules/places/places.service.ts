import { Injectable, NotFoundException } from '@nestjs/common';
import { DrizzleService } from '../../drizzle/drizzle.service';
import { places, Place, NewPlace } from '../../drizzle/schemas/places.schema';
import { eq, like, and, gte, lte, sql } from 'drizzle-orm';
import { CreatePlaceDto } from './dto/create-place.dto';
import { QueryPlacesDto } from './dto/query-places.dto';
import { calculateHaversineDistance, getBoundingBox } from '../../common/utils/spatial.util';

@Injectable()
export class PlacesService {
  constructor(private readonly drizzle: DrizzleService) {}

  async findAll(query: QueryPlacesDto): Promise<{ total: number; data: (Place & { distanceKm?: number })[] }> {
    const conditions: any[] = [];

    if (query.categoryId) {
      conditions.push(eq(places.categoryId, query.categoryId));
    }

    if (query.district) {
      conditions.push(like(places.district, `%${query.district}%`));
    }

    if (query.search) {
      conditions.push(
        sql`(${places.name} LIKE ${`%${query.search}%`} OR ${places.address} LIKE ${`%${query.search}%`})`,
      );
    }

    // Fast Bounding Box pre-filter if coordinates and radius provided
    if (query.lat && query.lng && query.radiusKm) {
      const bbox = getBoundingBox(query.lat, query.lng, query.radiusKm);
      conditions.push(
        gte(places.latitude, String(bbox.minLat)),
        lte(places.latitude, String(bbox.maxLat)),
        gte(places.longitude, String(bbox.minLng)),
        lte(places.longitude, String(bbox.maxLng)),
      );
    }

    const whereClause = conditions.length > 0 ? and(...conditions) : undefined;

    let result = await this.drizzle
      .select()
      .from(places)
      .where(whereClause);

    // Calculate exact Haversine distance and filter by radiusKm
    if (query.lat && query.lng) {
      const userLat = Number(query.lat);
      const userLng = Number(query.lng);

      const withDistance = result.map((p) => {
        const pLat = Number(p.latitude);
        const pLng = Number(p.longitude);
        const distanceKm = calculateHaversineDistance(userLat, userLng, pLat, pLng);
        return {
          ...p,
          distanceKm,
        };
      });

      let filtered = withDistance;
      if (query.radiusKm) {
        filtered = withDistance.filter((p) => p.distanceKm <= query.radiusKm);
      }

      // Sort by distance ascending
      filtered.sort((a, b) => a.distanceKm - b.distanceKm);

      const limit = query.limit || 50;
      const offset = query.offset || 0;
      const paginated = filtered.slice(offset, offset + limit);

      return {
        total: filtered.length,
        data: paginated,
      };
    }

    const limit = query.limit || 50;
    const offset = query.offset || 0;
    const paginated = result.slice(offset, offset + limit);

    return {
      total: result.length,
      data: paginated,
    };
  }

  async findById(id: number): Promise<Place> {
    const result = await this.drizzle
      .select()
      .from(places)
      .where(eq(places.id, id))
      .limit(1);

    if (!result || result.length === 0) {
      throw new NotFoundException(`Không tìm thấy địa điểm với ID ${id}`);
    }
    return result[0];
  }

  async create(dto: CreatePlaceDto): Promise<Place> {
    const insertData: NewPlace = {
      categoryId: dto.categoryId,
      name: dto.name,
      address: dto.address || null,
      district: dto.district || null,
      ward: dto.ward || null,
      latitude: String(dto.latitude),
      longitude: String(dto.longitude),
      rating: String(dto.rating || 4.0),
      userRatingsTotal: dto.userRatingsTotal || 0,
      priceAvg: dto.priceAvg || 35000,
      priceLevel: dto.priceLevel || 2,
      popularity: dto.popularity || 50,
      matchPreference: String(dto.matchPreference || 0.8),
      imageUrl: dto.imageUrl || null,
      openingHours: dto.openingHours || null,
      phoneNumber: dto.phoneNumber || null,
      description: dto.description || null,
    };

    const res = await this.drizzle.insert(places).values(insertData);
    const insertId = (res[0] as any).insertId;
    return this.findById(insertId);
  }

  async countTotal(): Promise<number> {
    const result = await this.drizzle.select({ count: sql<number>`count(*)` }).from(places);
    return Number(result[0]?.count || 0);
  }
}
