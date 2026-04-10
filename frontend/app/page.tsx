import { apiFetch } from "@/lib/api";

async function getApiHealth(): Promise<{ status: string } | null> {
  try {
    return await apiFetch<{ status: string }>("/health");
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await getApiHealth();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-bold mb-4">Game Promo Hub</h1>
      <p className="text-lg text-gray-600 mb-8">インディーゲームのプロモーション管理ツール</p>
      <div className="rounded-lg border p-6 text-center">
        <p className="text-sm text-gray-500 mb-1">API ステータス</p>
        {health ? (
          <span className="text-green-600 font-semibold">✅ {health.status}</span>
        ) : (
          <span className="text-red-500 font-semibold">❌ 接続できません</span>
        )}
      </div>
    </main>
  );
}
