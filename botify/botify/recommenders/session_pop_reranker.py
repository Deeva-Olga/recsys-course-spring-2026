"""SessionPopReranker: lightweight session-aware reranker.
Combines SasRec I2I candidates with simple popularity + diversity scoring.
Unique implementation: manual weights + adaptive artist penalty.
"""
import json
import math
from collections import Counter
from .recommender import Recommender


MAX_CANDIDATES = 35
RECENCY_DECAY = 0.85
ARTIST_PENALTY_BASE = 0.18
POPULARITY_BONUS = 0.12
MIN_LISTEN_TIME = 0.4


class SessionPopReranker(Recommender):
    def __init__(self, listen_history_redis, i2i_redis, catalog, fallback):
        self.listen_history_redis = listen_history_redis
        self.i2i_redis = i2i_redis
        self.fallback = fallback
        
        # Извлекаем артистов и "популярность" из каталога
        self.track_artist = {}
        self.track_pop_rank = {}
        
        for idx, track in enumerate(catalog.tracks):
            tid = int(track.track)
            self.track_artist[tid] = track.artist
            self.track_pop_rank[tid] = idx  # Позиция в каталоге = эвристика популярности
    
    def _load_history(self, user):
        """Загружает историю прослушиваний пользователя"""
        key = f"user:{user}:listens"
        raw = self.listen_history_redis.lrange(key, 0, -1)
        history = []
        for entry in raw:
            if isinstance(entry, bytes):
                entry = entry.decode("utf-8")
            data = json.loads(entry)
            history.append((int(data["track"]), float(data["time"])))
        return history
    
    def _get_candidates(self, anchor_track, seen):
        """Получает кандидатов из SasRec I2I для якорного трека"""
        raw = self.i2i_redis.get(anchor_track)
        if raw is None:
            return []
        
        # Поддерживаем и pickle, и JSON форматы
        try:
            import pickle
            candidates = pickle.loads(raw)
        except:
            candidates = json.loads(raw) if isinstance(raw, str) else raw
        
        return [int(c) for c in candidates[:MAX_CANDIDATES] if int(c) not in seen]
    
    def _score_candidate(self, candidate, history, anchor_rank, anchor_time):
        """Вычисляет скор для кандидата"""
        score = 0.0
        
        # 1. Бонус за высокий ранг в I2I рекомендациях
        rank_bonus = 1.0 / (anchor_rank + 1)
        score += rank_bonus
        
        # 2. Штраф за повторение артистов (адаптивный)
        candidate_artist = self.track_artist.get(candidate)
        if candidate_artist:
            # Считаем сколько раз артист уже был в сессии
            artist_count = sum(
                1 for t, _ in history 
                if self.track_artist.get(int(t)) == candidate_artist
            )
            # Адаптивный штраф: сильнее если артист уже часто встречался
            penalty = ARTIST_PENALTY_BASE * (artist_count ** 1.3)
            score -= penalty
        
        # 3. Бонус за популярность (уникальная фича)
        pop_rank = self.track_pop_rank.get(candidate, 9999)
        pop_bonus = POPULARITY_BONUS / math.log1p(pop_rank + 1)
        score += pop_bonus
        
        # 4. Бонус за "качество" якоря (если якорь долго слушали)
        if anchor_time >= MIN_LISTEN_TIME:
            score *= 1.15  # Усиливаем скор для хороших якорей
        
        return score
    
    def recommend_next(self, user, prev_track, prev_track_time):
        history = self._load_history(user)
        if not history:
            return self.fallback.recommend_next(user, prev_track, prev_track_time)
        
        seen = {int(t) for t, _ in history}
        
        # Выбираем "якоря" из недавней истории с затуханием
        anchors = []
        for i, (track, listened_time) in enumerate(reversed(history[:5])):
            weight = RECENCY_DECAY ** i
            anchors.append((int(track), listened_time, weight))
        
        # Собираем и скорим кандидатов
        candidate_scores = {}
        
        for anchor_track, anchor_time, anchor_weight in anchors:
            candidates = self._get_candidates(anchor_track, seen)
            
            for rank, candidate in enumerate(candidates):
                if candidate in seen or candidate == prev_track:
                    continue
                
                # Базовый скор + взвешивание по якорю
                base_score = self._score_candidate(candidate, history, rank, anchor_time)
                weighted_score = base_score * anchor_weight
                
                # Агрегируем скоры от разных якорей
                if candidate not in candidate_scores:
                    candidate_scores[candidate] = 0.0
                candidate_scores[candidate] += weighted_score
        
        if not candidate_scores:
            return self.fallback.recommend_next(user, prev_track, prev_track_time)
        
        # Возвращаем кандидата с максимальным скором
        best = max(candidate_scores.items(), key=lambda x: x[1])
        return int(best[0])
