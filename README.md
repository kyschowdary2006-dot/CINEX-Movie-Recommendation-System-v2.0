# CINEX — Movie Recommendation System v2.0

FastAPI + SQLite + scikit-learn ML — CINEX visual experience.

---
```
## Project Structure

CINEX-Movie-Recommendation-System-v2.0/     # Root folder of the CINEX project
│
├── app/                                    # Main backend application folder
│   │
│   ├── main.py                             # Entry point of FastAPI/Flask application
│   ├── config.py                           # Application configuration settings
│   ├── dependencies.py                     # Shared dependencies and helper functions
│   │
│   ├── api/                                # API routing layer
│   │   ├── router.py                       # Combines and manages all API routes
│   │   │
│   │   └── routes/                         # Individual API route files
│   │       ├── users.py                    # User authentication and profile routes
│   │       ├── movies.py                   # Movie data handling routes
│   │       ├── recommend.py                # Recommendation system routes
│   │       └── ratings.py                  # Movie ratings and reviews routes
│   │
│   ├── agent/                              # AI/Groq/CrewAI related modules
│   │   ├── agent.py                        # Main AI agent implementation
│   │   ├── prompts.py                      # Prompt templates for AI interactions
│   │   ├── memory.py                       # AI memory/context management
│   │   └── tools.py                        # Custom AI tools and helper utilities
│   │
│   ├── db/                                 # Database-related files
│   │   └── init_db.py                      # Database initialization script
│   │
│   ├── ml/                                 # Machine Learning modules
│   │   ├── predict.py                      # Generates movie recommendations
│   │   ├── preprocessing.py                # Data cleaning and preprocessing
│   │   ├── train.py                        # ML model training script
│   │   │
│   │   └── store/                          # Saved ML models and datasets
│   │       ├── movie_index.pkl             # Indexed movie dataset
│   │       ├── tfidf_vectorizer.pkl        # Saved TF-IDF vectorizer
│   │       ├── movie_meta.pkl              # Movie metadata storage
│   │       └── tfidf_matrix.pkl            # TF-IDF feature matrix
│   │
│   ├── models/                             # Database models/classes
│   │   ├── movie.py                        # Movie model definition
│   │   ├── rating.py                       # Rating model definition
│   │   └── user.py                         # User model definition
│   │
│   ├── schemas/                            # API validation schemas
│   │   ├── user_schema.py                  # User request/response schemas
│   │   ├── movie_schema.py                 # Movie request/response schemas
│   │   └── rating_schema.py                # Rating request/response schemas
│   │
│   └── services/                           # Business logic layer
│       ├── movie_service.py                # Handles movie-related operations
│       ├── rating_service.py               # Handles ratings and reviews logic
│       ├── recommender.py                  # Core recommendation engine
│       └── user_service.py                 # User management logic
│
├── public/                                 # Frontend/static website files
│   ├── index.html                          # Main frontend webpage
│   ├── style.css                           # Frontend styling
│   └── script.js                           # Frontend JavaScript functionality
│
├── .env                                    # Environment variables and secret keys
├── Dockerfile                              # Docker image configuration file
├── docker-compose.yml                      # Multi-container Docker setup
├── requirements.txt                        # Python package dependencies
├── users.db                                # SQLite database storing user information
│
└── README.md                               # Project documentation and setup guide

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
