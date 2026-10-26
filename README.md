# 4ILGAMES Xbox Catalog — GitHub Pages

Автоматически получает список Xbox-игр из Telegraph и пересчитывает цены RUB → BYN по официальному курсу НБРБ без наценки. Создаёт сайт с поиском.

## Установка в существующий репозиторий

1. Замените файлы `sync.py`, `requirements.txt`, `.github/workflows/sync.yml` файлами из этого архива. Сохраните структуру папок.
2. Откройте **Settings → Pages → Build and deployment → Source** и выберите **GitHub Actions**.
3. Откройте **Actions → Update Xbox catalog website → Run workflow**.
4. После успешного запуска откройте https://tomeyanyan.github.io/4ilgames-xbox-catalog/ . Иногда публикация занимает несколько минут.

GitHub Actions запускает обновление каждый день в **10:15 по Минску** (07:15 UTC). Для GitHub Pages не нужен `TELEGRAPH_TOKEN`. Старый `state.json` можно оставить, он не используется. Если GitHub Actions требует подтверждения включения Pages, сделайте это в Settings → Pages.

**Важно:** расписание GitHub Actions может иногда запускаться с задержкой; точность до минуты не гарантируется. Исходный список может содержать текстовые строки без цен, поэтому число строк и число конвертированных цен различаются.
