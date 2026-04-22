# generate_hstu_recs.py
"""
Генерирует рекомендации для HSTU treatment
Формат: JSONL → botify/data/hstu_recommendations.json
"""

import json
import random
import numpy as np
import os
from collections import Counter, defaultdict
from pathlib import Path

# Настройки
N_USERS = 10000
RECS_PER_USER = 20
RANDOM_SEED = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

def load_data():
    """Пытается загрузить данные, иначе генерирует синтетические"""
    import pandas as pd
    
    paths = [
        'botify/data/train_interactions.csv',
        'botify/data/train.json', 
        'data/train_interactions.csv',
    ]
    
    for path in paths:
        if Path(path).exists():
            print(f"✅ Loaded: {path}")
            if path.endswith('.csv'):
                return pd.read_csv(path)
            else:
                data = [json.loads(line) for line in open(path) if line.strip()]
                return pd.DataFrame(data)
    
    # Синтетические данные
    print("⚠️  Generating synthetic data...")
    n_users, n_tracks, n_artists = 1000, 5000, 200
    data = []
    for _ in range(50000):
        data.append({
            'user_id': random.randint(0, n_users-1),
            'track_id': random.randint(0, n_tracks-1),
            'artist_id': random.randint(0, n_artists-1),
            'time': random.expovariate(1.0)
        })
    return pd.DataFrame(data)

def compute_features(df):
    """Вычисляет фичи для рекомендаций"""
    track_pop = df['track_id'].value_counts().to_dict()
    max_t = max(track_pop.values()) if track_pop else 1
    track_pop_norm = {k: v/max_t for k, v in track_pop.items()}
    
    artist_pop = df['artist_id'].value_counts().to_dict()
    max_a = max(artist_pop.values()) if artist_pop else 1
    artist_pop_norm = {k: v/max_a for k, v in artist_pop.items()}
    
    track_artist = dict(zip(df['track_id'], df['artist_id']))
    
    user_prefs = defaultdict(lambda: {'artists': Counter(), 'tracks': Counter()})
    for _, row in df.iterrows():
        uid = row['user_id']
        user_prefs[uid]['artists'][row['artist_id']] += 1
        user_prefs[uid]['tracks'][row['track_id']] += row.get('time', 1.0)
    
    return {
        'track_pop': track_pop_norm,
        'artist_pop': artist_pop_norm,
        'track_artist': track_artist,
        'user_prefs': user_prefs,
        'all_tracks': list(track_artist.keys())
    }

def generate_recs_for_user(user_id, features):
    """Генерирует топ-20 треков для пользователя"""
    prefs = features['user_prefs'].get(user_id, {'artists': Counter(), 'tracks': Counter()})
    track_pop = features['track_pop']
    track_artist = features['track_artist']
    all_tracks = features['all_tracks']
    
    candidates = []
    seen = set(prefs['tracks'].keys())
    
    # 1. Уже слушанные треки
    for track, score in prefs['tracks'].most_common(5):
        candidates.append((int(track), 1.0 + 0.2 * score))
    
    # 2. Треки от любимых артистов
    for artist, artist_score in prefs['artists'].most_common(3):
        for track, t_artist in track_artist.items():
            if t_artist == artist and track not in seen:
                pop = track_pop.get(track, 0.1)
                score = 0.6 + 0.2 * min(artist_score/10, 1) + 0.2 * pop
                candidates.append((int(track), score))
    
    # 3. Популярные треки
    for track, pop in sorted(track_pop.items(), key=lambda x: -x[1])[:100]:
        if track not in seen and track not in [c[0] for c in candidates]:
            candidates.append((int(track), 0.4 + 0.3 * pop))
    
    # 4. Случайные для exploration
    if len(candidates) < RECS_PER_USER:
        remaining = [t for t in all_tracks if t not in seen and t not in [c[0] for c in candidates]]
        for track in random.sample(remaining, min(50, len(remaining))):
            candidates.append((int(track), 0.1 + 0.1 * random.random()))
    
    candidates = sorted(candidates, key=lambda x: -x[1])
    return [c[0] for c in candidates[:RECS_PER_USER]]

def main():
    print("🔧 Loading data...")
    df = load_data()
    
    print("📊 Computing features...")
    features = compute_features(df)
    print(f"   Tracks: {len(features['all_tracks'])}")
    
    output_path = Path('botify/botify/data/hstu_recommendations.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎯 Generating {N_USERS} user recommendations...")
    
    with open(str(output_path), 'w', encoding='utf-8') as f:  # ← str() + encoding
        for user_id in range(N_USERS):
            recs = generate_recs_for_user(user_id, features)
            line = json.dumps({"user": int(user_id), "tracks": recs}, ensure_ascii=False)
            f.write(line + '\n')
            
            if user_id % 1000 == 0:
                print(f"   Progress: {user_id}/{N_USERS}")
    
    size_mb = output_path.stat().st_size / (1024*1024)
    print(f"\n✅ Done!")
    print(f"   File: {output_path}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"   Lines: {N_USERS}")
    
    with open(str(output_path), encoding='utf-8') as f:  # ← str() + encoding
        sample = json.loads(f.readline())
        print(f"   Sample: {json.dumps(sample, ensure_ascii=False)[:100]}...")
        print(f"   Тип первого трека: {type(sample['tracks'][0]).__name__}")

if __name__ == '__main__':
    main()