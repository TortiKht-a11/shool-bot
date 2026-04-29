# School Bot — приём заявок в 1 класс

Этот проект — production-ready Telegram-бот на **aiogram 3.x** для приёма заявок на поступление **только в 1 класс**.  
Бот помогает родителям подать заявление и загрузить документы, а приёмной комиссии (админам) — просматривать заявки, менять статусы, оставлять комментарии, экспортировать данные в Excel и делать рассылку.

## Информация о школе

- **Полное название:** МБОУ СОШ Образовательный Центр "Новый город"
- **Краткое название:** школа "Новый город"
- **Город:** г. Владикавказ
- **Адрес:** ул. Билара Кабалоева, 14
- **Сайт:** https://sh-oc-novyj-gorod-vladikavkaz-r90.gosweb.gosuslugi.ru/
- **Приём:** только в 1 класс
- **Контактное лицо:** Завуч Диана Казбековна
- **Телефон:** +7 (928) 688-63-21
- **Часы работы приёмной комиссии:** Пн-Пт, 9:00-17:00

## Установка и запуск

```bash
git clone <repo>
cd school_bot
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
cp .env.example .env
# отредактировать .env
python main.py
```

### Как получить токен у @BotFather

1. Откройте Telegram и найдите `@BotFather`.
2. Создайте нового бота командой `/newbot`.
3. Скопируйте токен и вставьте в `.env` как `BOT_TOKEN=...`.

### Как узнать свой user_id через @userinfobot

1. Откройте Telegram и найдите `@userinfobot`.
2. Нажмите Start — бот покажет ваш `user_id`.
3. Добавьте ID в `.env` в `ADMIN_IDS` (через запятую), если нужен доступ админа.

## Структура проекта

```
school_bot/
├── main.py
├── config.py
├── .env.example
├── requirements.txt
├── README.md
├── bot.log                # создаётся автоматически
├── school.db              # создаётся автоматически
├── uploads/               # создаётся автоматически
├── handlers/
├── states/
├── keyboards/
├── db/
└── utils/
```

## Скриншоты

- (placeholder) Главное меню
- (placeholder) Подача заявления
- (placeholder) Админ-панель

## Лицензия

MIT
