/**
 * Spatial calculation utilities for Location-Based Decision Support System
 */

const EARTH_RADIUS_KM = 6371;

/**
 * Calculates the great-circle distance between two points on the Earth's surface
 * using the Haversine formula.
 * @param lat1 Latitude of point 1 in degrees
 * @param lon1 Longitude of point 1 in degrees
 * @param lat2 Latitude of point 2 in degrees
 * @param lon2 Longitude of point 2 in degrees
 * @returns Distance in kilometers
 */
export function calculateHaversineDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) *
      Math.cos(toRadians(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distance = EARTH_RADIUS_KM * c;

  // Round to 2 decimal places
  return Math.round(distance * 100) / 100;
}

/**
 * Calculate rough bounding box coordinates for fast DB indexing
 * @param centerLat Center latitude
 * @param centerLng Center longitude
 * @param radiusKm Radius in kilometers
 */
export function getBoundingBox(
  centerLat: number,
  centerLng: number,
  radiusKm: number,
): { minLat: number; maxLat: number; minLng: number; maxLng: number } {
  // 1 degree latitude ~ 111.32 km
  const latDelta = radiusKm / 111.32;
  // 1 degree longitude ~ 111.32 * cos(lat) km
  const lngDelta = radiusKm / (111.32 * Math.cos(toRadians(centerLat)));

  return {
    minLat: centerLat - latDelta,
    maxLat: centerLat + latDelta,
    minLng: centerLng - lngDelta,
    maxLng: centerLng + lngDelta,
  };
}

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}
