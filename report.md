## Homework 2 Report

## Abstract
Мы предлагаем улучшить рекомендательную систему Botify, заменив precomputed рекомендации для HSTU treatment на гибридную модель, сочетающую user-based персонализацию и global popularity ranking. В отличие от бейзлайна SasRec-I2I (item-to-item сессионный), наша модель учитывает историю прослушиваний пользователя, предпочтения по артистам и популярность треков, что улучшает баланс реелевантности и диверсификации. В A/B тесте ожидаем статистически значимое улучшение метрики mean_time_per_session.

## Детали реализации

### Архитектура модели

User ID → [Load User Preferences]
1. User History Scoring 
- Ранее слушанные треки: +1.0 base
- Weight by listen time
2. Artist Affinity Scoring
- Треки от любимых артистов: +0.6 base
- Bonus by artist popularity
3. Global Popularity Scoring
- Топ-100 популярных треков: +0.4 base
- Для cold-start и diversity
4. Exploration (random sampling)
- Случайные треки для исследования
Hybrid Score = weighted_sum(components) │
Top-20 tracks → JSONL → Redis


### Формат данных
Файл: `botify/data/hstu_recommendations.json`
Формат: JSONL (JSON Lines), одна запись на строку:
json
{"user": 12345, "tracks": [67890, 11111, 22222, ..., 99999]}
user: int, ID пользователя (0..9999)
tracks: list[int], 20 рекомендованных track_id

### Ключевые идеи
Artist affinity: треки от артистов, которых пользователь часто слушал, получают бонус к скору
Recency + duration weighting: недавние и долгие прослушивания влияют сильнее
Popularity tail: глобально популярные треки помогают при cold-start и увеличивают diversity
Controlled exploration: случайные треки с низким весом позволяют модели исследовать новые предпочтения
