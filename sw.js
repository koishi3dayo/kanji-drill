// 漢字ドリル Service Worker（オフライン起動用）
// キャッシュのバージョン。アプリ更新時はこの数字を上げると自動で新版に切り替わる。
const CACHE = 'kanji-drill-v1';

const ASSETS = [
  './',
  './index.html',
  './kanji-data.js?v=3',
  './sentence-data.js?v=3',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-512-maskable.png',
  './icons/icon-180.png'
];

// インストール時に必要ファイルを先読みキャッシュ
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

// 新バージョン有効化時に古いキャッシュを削除
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// キャッシュ優先（オフラインでも起動）。無ければネットワークへ。
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request).then((cached) => {
      if (cached) return cached;
      return fetch(e.request).then((res) => {
        // 取得したものは同一オリジンのみキャッシュに追加
        if (res.ok && e.request.url.startsWith(self.location.origin)) {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, clone));
        }
        return res;
      }).catch(() => cached);
    })
  );
});
