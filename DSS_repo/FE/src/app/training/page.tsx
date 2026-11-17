import Link from 'next/link';
import TrainingArtifacts from '@/components/training-artifacts';

export default function TrainingPage() {
  return <main className="report-page"><Link href="/" className="text-button">← Khám phá Đà Nẵng</Link><h1>Kết quả <em>huấn luyện.</em></h1><p>Đối chiếu mô hình trên Đà Nẵng và Gowalla từ bộ artifacts Colab.</p><TrainingArtifacts/></main>;
}
