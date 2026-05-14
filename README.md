# CINEX — Movie Recommendation System v2.0

FastAPI + SQLite + scikit-learn ML — CINEX visual experience.

---

## Project Structure

```
cinex_groq/
│
├── .env
├── requirements.txt
│
├── public/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── app/
│   │
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   │
│   ├── api/
│   │   ├── router.py
│   │   │
│   │   └── routes/
│   │       ├── users.py
│   │       ├── movies.py
│   │       ├── recommend.py
│   │       └── ratings.py
│   │
│   ├── agent/
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   ├── memory.py
│   │   └── tools.py
│   │
│   ├── db/
│   │   └── init_db.py
│   │
│   ├── ml/
│   │   ├── predict.py
│   │   ├── preprocessing.py
│   │   ├── train.py
│   │   │
│   │   └── store/
│   │       ├── movie_index.pkl
│   │       ├── tfidf_vectorizer.pkl
│   │       ├── movie_meta.pkl
│   │       └── tfidf_matrix.pkl
│   │
│   ├── models/
│   │   ├── movie.py
│   │   ├── rating.py
│   │   └── user.py
│   │
│   ├── schemas/
│   │   ├── user_schema.py
│   │   ├── movie_schema.py
│   │   └── rating_schema.py
│   │
│   └── services/
│       ├── movie_service.py
│       ├── rating_service.py
│       ├── recommender.py
│       └── user_service.py
│
└── README.md (recommended to add)
```

---

## Quickstart

### 1 — Install
```bash
pip install -r requirements.txt
```

### 2 — Start server
```bash
uvicorn app.main:app --reload
```
Open **http://localhost:8000** — `users.db` is created automatically.

### 3 — Train ML (run once)
```bash
python -m app.ml.train --fetch
```
Fetches ~500 movies from TMDB → stores in `movies` table → trains TF-IDF + SVD.

### 4 — Run tests
```bash
pytest tests/ -v
```

### Docker
```bash
docker compose up --build
```

---

## API Routes

### Auth  `/api/auth/…`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register → saves to users.db |
| POST | `/api/auth/login`    | Login → JWT token |
| GET  | `/api/auth/me`       | Current user (JWT required) |

### Movies  `/api/movies/…`
| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/movies/watchlist`        | Get user's watchlist |
| POST   | `/api/movies/watchlist`        | Add to watchlist |
| DELETE | `/api/movies/watchlist/{id}`   | Remove from watchlist |
| POST   | `/api/movies/fetch`            | Trigger TMDB fetch + retrain |

### Ratings  `/api/ratings/…`
| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/ratings/{movie_id}`      | Community avg + my rating |
| POST   | `/api/ratings`                 | Rate a movie (1–5 ★) |
| GET    | `/api/ratings/comments/{id}`   | Get comments |
| POST   | `/api/ratings/comments`        | Post a comment |
| DELETE | `/api/ratings/comments/{id}`   | Delete own comment |

### Recommendations  `/api/recommend/…`
| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/recommend/{movie_id}`    | Hybrid recs for a movie |
| GET  | `/api/recommend/user/me`       | Personalised home feed |
| GET  | `/api/recommend/status/models` | ML artefact + DB status |
| POST | `/api/recommend/train`         | Trigger training (background) |

Interactive docs: **http://localhost:8000/docs**

---

## ML Pipeline

```
python -m app.ml.train --fetch
         │
         ├─ Step 1: movie_service.fetch_and_store()
         │    Async TMDB fetch → upserts movies table in users.db
         │
         ├─ Step 2: preprocessing.run()
         │    genres + overview + cast + keywords → TF-IDF matrix
         │    Saves: tfidf_matrix.pkl, movie_index.pkl, movie_meta.pkl
         │
         └─ Step 3: collaborative SVD
              ratings table → user×movie matrix → TruncatedSVD(k=50)
              Saves: collab_predicted.pkl, collab_user_map.pkl, collab_movie_map.pkl
```

### Hybrid blending
| Situation | Content weight | Collab weight |
|-----------|---------------|---------------|
| New/anonymous user | 85% | 15% |
| User with ratings  | 45% | 55% |

---

## Inspect users.db

```bash
sqlite3 users.db ".tables"
sqlite3 users.db "SELECT id, username, email FROM users;"
sqlite3 users.db "SELECT COUNT(*) FROM movies;"
sqlite3 users.db "SELECT u.username, r.movie_id, r.rating FROM ratings r JOIN users u ON r.user_id=u.id;"
```
