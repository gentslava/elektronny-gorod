# Публикация сайта

Сайт — статическая сборка (`npm run build` → `website/dist/`), подходит любой
статический хостинг. Секретов и серверной части нет.

## Вариант 1: GitHub Pages (используется)

Workflow подключён: [`.github/workflows/website.yml`](../../.github/workflows/website.yml).
Он срабатывает на push в `master` с изменениями внутри `website/**`
(и вручную через workflow_dispatch), прогоняет typecheck + тесты + сборку
и публикует `website/dist` на Pages. Источник Pages в настройках репозитория —
**GitHub Actions**.

Адрес: `https://gentslava.github.io/elektronny-gorod/`. Сборка использует
`base: './'`, поэтому работает и в подпапке Pages, и на собственном домене.

Workflow затрагивает только `website/**` (path-filter) и не пересекается с
релизным пайплайном интеграции (`release.yaml`, `prerelease.yaml`).

## Вариант 2: Cloudflare Pages / Vercel / Netlify

- Build command: `cd website && npm ci && npm run build`
- Output directory: `website/dist`
- Node: 20+

## Вариант 3: свой сервер

```bash
cd website && npm ci && npm run build
rsync -a dist/ user@host:/var/www/elektronny-gorod/
```

## После смены домена

Обновите canonical/OG-URL в `index.html` (см. [`sync.md`](sync.md)).
