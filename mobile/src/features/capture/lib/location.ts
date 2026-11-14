import * as Location from 'expo-location';
import type { CaptureDraft } from '@/domain/models';
export async function captureLocation(): Promise<NonNullable<CaptureDraft['captureLocation']>> {
  const permission = await Location.requestForegroundPermissionsAsync();
  if (!permission.granted)
    throw new Error(
      'Cần quyền vị trí để xác minh đến nơi. Hãy cấp quyền trong cài đặt và thử lại.',
    );
  const sample = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
  const { latitude, longitude, accuracy } = sample.coords;
  if (accuracy === null || !Number.isFinite(accuracy) || accuracy < 0 || accuracy > 50)
    throw new Error('GPS chưa đủ chính xác (cần ≤50 m). Hãy ra nơi thoáng và lấy lại vị trí.');
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    Math.abs(latitude) > 90 ||
    Math.abs(longitude) > 180 ||
    !Number.isFinite(sample.timestamp)
  )
    throw new Error('Vị trí không hợp lệ. Hãy lấy lại GPS.');
  const age = Date.now() - sample.timestamp;
  if (age > 60000 || age < -5000)
    throw new Error('Vị trí đã cũ hoặc đồng hồ chưa đúng. Hãy lấy lại GPS.');
  return {
    latitude,
    longitude,
    accuracy_m: accuracy,
    captured_at: new Date(sample.timestamp).toISOString(),
    source: 'gps',
  };
}
