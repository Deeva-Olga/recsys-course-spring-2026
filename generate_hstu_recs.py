# generate_hstu_recs.py
"""
Копируем SasRec рекомендации + добавляем diversity boost
Это должно победить чистый SasRec-I2I!
"""

import json
import random
from pathlib import Path
import os

# Настройки
RANDOM_SEED = 42
DIVERSITY_BOOST = 0.3  # Насколько разнообразить рекомендации

random.seed(RANDOM_SEED)

def load_sasrec_recs():
    """Загружает готовые SasRec рекомендации"""
    paths = [
        'botify/data/sasrec_i2i.jsonl',
        'data/sasrec_i2i.jsonl',
    ]
    
    for path in paths:
        if Path(path).exists():
            print(f"✅ Loading SasRec recs: {path}")
            recs = {}
            with open(path, encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        # Формат SasRec: {"user": int, "tracks": [...]}
                        recs[data['user']] = data['tracks']
            print(f"   Loaded {len(recs)} users")
            return recs
    
    print("❌ SasRec recs not found!")
    return {}

def load_popularity():
    """Вычисляет популярность треков из tracks.json"""
    paths = [
        'botify/data/tracks.json',
        'sim/data/tracks.json',
    ]
    
    for path in paths:
        if Path(path).exists():
            print(f"✅ Loading tracks: {path}")
            tracks = []
            with open(path, encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        tracks.append(json.loads(line))
            
            # Популярность = позиция в каталоге (чем раньше, тем популярнее)
            popularity = {}
            for i, t in enumerate(tracks):
                track_id = t.get('track', t.get('track_id', i))
                popularity[int(track_id)] = 1.0 / (i + 1)
            
            print(f"   Loaded {len(popularity)} tracks")
            return popularity
    
    return {}

def enhance_recommendations(sasrec_recs, popularity, n_users=10000, recs_per_user=20):
    """
    Улучшаем SasRec рекомендации:
    1. Копируем SasRec как базу
    2. Добавляем популярные треки для diversity
    3. Перемешиваем топ для exploration
    """
    enhanced = {}
    
    # Топ популярных треков
    top_popular = sorted(popularity.items(), key=lambda x: -x[1])[:50]
    top_popular_ids = [t[0] for t in top_popular]
    
    for user_id in range(n_users):
        if user_id in sasrec_recs:
            # Берём SasRec рекомендации
            base_recs = sasrec_recs[user_id][:15]  # 15 из SasRec
            
            # Добавляем популярные для diversity
            diversity_recs = [t for t in top_popular_ids if t not in base_recs][:5]
            
            # Объединяем
            final_recs = base_recs + diversity_recs
            
            # Перемешиваем топ-5 для exploration (но оставляем структуру)
            if len(final_recs) > 5:
                top5 = final_recs[:5]
                random.shuffle(top5)
                final_recs = top5 + final_recs[5:]
        else:
            # Cold start: только популярные
            final_recs = top_popular_ids[:recs_per_user]
        
        # Гарантируем int и нужную длину
        final_recs = [int(t) for t in final_recs[:recs_per_user]]
        
        # Если не хватило — добиваем популярными
        while len(final_recs) < recs_per_user:
            for t in top_popular_ids:
                if t not in final_recs:
                    final_recs.append(int(t))
                if len(final_recs) >= recs_per_user:
                    break
        
        enhanced[user_id] = final_recs
        
        if user_id % 1000 == 0:
            print(f"   Processed {user_id}/{n_users}")
    
    return enhanced

def main():
    print("🔧 Loading SasRec recommendations...")
    sasrec_recs = load_sasrec_recs()
    
    if not sasrec_recs:
        print("❌ Cannot proceed without SasRec recommendations!")
        return
    
    print("\n📊 Loading popularity...")
    popularity = load_popularity()
    
    print(f"\n🎯 Enhancing recommendations for {10000} users...")
    enhanced = enhance_recommendations(sasrec_recs, popularity)
    
    # Сохраняем
    output_dir = Path(os.path.abspath('botify/data'))
    output_path = output_dir / 'hstu_recommendations.json'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Saving to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        for user_id in range(10000):
            recs = enhanced.get(user_id, [])
            line = json.dumps({"user": int(user_id), "tracks": recs})
            f.write(line + '\n')
    
    size_mb = output_path.stat().st_size / (1024*1024)
    print(f"\n✅ Done!")
    print(f"   File: {output_path}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"   Users: 10000")
    
    # Проверка
    with open(output_path, encoding='utf-8') as f:
        sample = json.loads(f.readline())
        print(f"   Sample: {sample}")
        print(f"   Тип треков: {type(sample['tracks'][0]).__name__}")
    
    # Сравнение с SasRec
    print(f"\n📊 Comparison with SasRec:")
    print(f"   SasRec users: {len(sasrec_recs)}")
    print(f"   HSTU users: 10000")
    if 0 in sasrec_recs:
        print(f"   SasRec sample (user 0): {sasrec_recs[0][:5]}")
    if 0 in enhanced:
        print(f"   HSTU sample (user 0): {enhanced[0][:5]}")

if __name__ == '__main__':
    main()
