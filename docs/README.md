# Telegram Bot NFT — Документация

Документация для [Telegram Bot NFT](https://github.com/fitymico/tgbotnft) на базе [Docusaurus](https://docusaurus.io/).

Сайт: https://pluttan.github.io/Telegram-Bot-NFT-docs/

> Эта папка является частью монорепозитория [fitymico/tgbotnft](https://github.com/fitymico/tgbotnft) и одновременно синхронизируется с отдельным репозиторием [fitymico/tgbotnft-docs](https://github.com/fitymico/tgbotnft-docs) через `git subtree`.

## Локальная разработка

```bash
npm install
npm start        # http://localhost:3000
```

## Сборка

```bash
npm run build    # Статика в директории build/
```

## Деплой

Автоматический деплой на GitHub Pages через GitHub Actions при пуше в `main` репозитория [fitymico/tgbotnft-docs](https://github.com/fitymico/tgbotnft-docs).

## Синхронизация с монорепо

```bash
# Пуш docs в отдельный репозиторий
git subtree push --prefix=docs docs-origin main

# Подтянуть изменения из отдельного репозитория
git subtree pull --prefix=docs docs-origin main --squash
```
