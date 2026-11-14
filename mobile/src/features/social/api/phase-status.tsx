import { Text } from 'react-native';
import { Page } from '@/shared/components/page';
import { Action } from '@/shared/components/action';
import { commonStyles as c } from '@/shared/components/surface';

export function ApiExplore() {
  return (
    <Page title="Khám phá">
      <Text style={c.body}>Tiến trình và nhiệm vụ đang chờ tích hợp.</Text>
      <Action label="Bộ sưu tập thử nghiệm" href="/(main)/collection" />
    </Page>
  );
}

export function ApiCapture() {
  return (
    <Page title="Máy ảnh">
      <Text style={c.body}>Tải ảnh và đánh giá đang chờ tích hợp.</Text>
      <Action label="Bộ sưu tập thử nghiệm" href="/(main)/collection" />
    </Page>
  );
}
