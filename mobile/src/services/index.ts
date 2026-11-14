import { mockMissionService } from '@/services/mock/mission-service';
import { listTimeline } from '@/services/api/capture';
import { env } from '@/config/env';
import type { ExplorationService, FeedService, MissionService } from '@/services/contracts';
import { mockExplorationService, mockFeedService } from '@/services/mock';

async function notIntegrated(): Promise<never> {
  throw new Error('API mới chưa được tích hợp. Dùng EXPO_PUBLIC_DATA_SOURCE=mock để dựng UI.');
}
const apiExplorationService: ExplorationService = { listEras: listTimeline };
const apiFeedService: FeedService = { listPosts: notIntegrated };
// Never silently fall back to fixtures when a real API fails.
const apiMissionService: MissionService = { search: notIntegrated };
export const services = {
  missions: env.dataSource === 'mock' ? mockMissionService : apiMissionService,
  exploration: env.dataSource === 'mock' ? mockExplorationService : apiExplorationService,
  feed: env.dataSource === 'mock' ? mockFeedService : apiFeedService,
};
