# 🎬 CINEX — Movie Recommendation System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Groq-AI%20Agent-F55036?style=for-the-badge&logo=groq&logoColor=white"/>
  <img src="https://img.shields.io/badge/scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white"/>
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white"/>
</p>

<p align="center">
  A full-stack movie recommendation web app powered by a hybrid ML engine (TF-IDF + SVD), a Groq AI chat agent, JWT authentication, and live TMDB data.
</p>

---

## ✨ Features

- 🤖 **AI Chat Agent** — Groq-powered assistant for movie search & recommendations
- 🎯 **Hybrid ML Engine** — Content-based (TF-IDF) + Collaborative filtering (SVD) blended recommendations
- 🔐 **JWT Authentication** — Secure register/login with bcrypt password hashing
- 🎥 **TMDB Integration** — Fetches live movie data (posters, overviews, cast, genres)
- ⭐ **Ratings & Comments** — Community rating system with user comments
- 📋 **Watchlist** — Personal movie watchlist per user
- 📧 **OTP Email Verification** — Via EmailJS integration
- 🐳 **Docker Ready** — One command deployment with Docker Compose
- 📖 **Interactive API Docs** — Auto-generated Swagger UI at `/docs`

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Uvicorn |
| Database | SQLite via SQLAlchemy ORM |
| Authentication | JWT (python-jose) + bcrypt |
| ML / AI | scikit-learn (TF-IDF, TruncatedSVD), Groq LLM |
| HTTP Client | httpx (async TMDB calls) |
| Frontend | Vanilla HTML + CSS + JavaScript |
| DevOps | Docker, Docker Compose |

---

## 📁 Project Structure

```
cinex_groq/
├── app/
│   ├── main.py                  ← FastAPI entry point
│   ├── config.py                ← Settings loaded from .env
│   ├── dependencies.py          ← Shared DB + auth dependencies
│   │
│   ├── api/
│   │   ├── router.py            ← Combines all route groups
│   │   └── routes/
│   │       ├── users.py         ← /api/users/*
│   │       ├── movies.py        ← /api/movies/*
│   │       ├── ratings.py       ← /api/ratings/*, /api/comments/*
│   │       └── recommend.py     ← /api/recommend/*
│   │
│   ├── services/                ← Business logic layer
│   ├── models/                  ← SQLAlchemy ORM models
│   ├── schemas/                 ← Pydantic request/response schemas
│   │
│   ├── ml/
│   │   ├── train.py             ← Full training pipeline CLI
│   │   ├── predict.py           ← Inference (content + collab + hybrid)
│   │   ├── preprocessing.py     ← TF-IDF feature engineering
│   │   └── store/               ← Pre-trained .pkl artifacts
│   │
│   ├── db/                      ← SQLAlchemy engine + DB init
│   ├── core/                    ← JWT security + structured logging
│   └── agent/                   ← Groq AI chat agent + memory + tools
│
├── public/                      ← Frontend (HTML + CSS + JS)
├── .env                         ← Environment variables
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## ⚡ Quickstart

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/cinex.git
cd cinex
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Linux / Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy or edit the `.env` file and fill in your keys:

```env
# JWT Secret — change this in production!
SECRET_KEY=cinex-super-secret-change-in-production-please

# TMDB API Key — get at https://developer.themoviedb.org
TMDB_API_KEY=your_tmdb_api_key_here

# Groq AI Agent — get FREE key at https://console.groq.com
GROQ_API_KEY=your_groq_api_key_here

# EmailJS (optional — for OTP email verification)
EMAILJS_PUBLIC_KEY=your_emailjs_public_key
EMAILJS_SERVICE_ID=your_service_id
EMAILJS_TEMPLATE_ID=your_template_id
```

### 5. Run the Server

```bash
uvicorn app.main:app --reload
```

- 🌐 App → **http://localhost:8000**
- 📖 API Docs → **http://localhost:8000/docs**
- 🗄️ `users.db` is created **automatically** on first run

### 6. Train the ML Models *(run once)*

> Pre-trained `.pkl` artifacts are already included — skip this step if you just want to run the app.

```bash
python -m app.ml.train --fetch
```

This will:
1. Fetch ~500 movies from TMDB
2. Build TF-IDF content vectors (genres + overview + cast + keywords)
3. Train TruncatedSVD (k=50) for collaborative filtering
4. Save all artifacts to `app/ml/store/`

---

## 🐳 Docker Deployment

```bash
docker compose up --build
```

---

## 🔌 API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login → returns JWT token |
| GET | `/api/auth/me` | Get current user (JWT required) |

### Movies
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/movies/watchlist` | Get user's watchlist |
| POST | `/api/movies/watchlist` | Add movie to watchlist |
| DELETE | `/api/movies/watchlist/{id}` | Remove from watchlist |
| POST | `/api/movies/fetch` | Trigger TMDB fetch + retrain |

### Ratings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ratings/{movie_id}` | Community avg + personal rating |
| POST | `/api/ratings` | Rate a movie (1–5 ★) |
| GET | `/api/ratings/comments/{id}` | Get comments for a movie |
| POST | `/api/ratings/comments` | Post a comment |
| DELETE | `/api/ratings/comments/{id}` | Delete own comment |

### Recommendations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/recommend/{movie_id}` | Hybrid recommendations for a movie |
| GET | `/api/recommend/user/me` | Personalised home feed |
| GET | `/api/recommend/status/models` | ML artifact + DB status |
| POST | `/api/recommend/train` | Trigger background retraining |

---

## 🧠 ML Pipeline

```
python -m app.ml.train --fetch
         │
         ├─ Step 1: Fetch movies from TMDB → upsert into users.db
         │
         ├─ Step 2: TF-IDF vectorization
         │    genres + overview + cast + keywords → sparse matrix
         │    Saves: tfidf_matrix.pkl, movie_index.pkl, movie_meta.pkl
         │
         └─ Step 3: Collaborative SVD
              ratings table → user × movie matrix → TruncatedSVD(k=50)
              Saves: collab_predicted.pkl, collab_user_map.pkl, collab_movie_map.pkl
```

### Hybrid Blending Strategy

| User Situation | Content Weight | Collab Weight |
|----------------|---------------|---------------|
| New / anonymous user | 85% | 15% |
| User with ratings | 45% | 55% |

---

## 🔑 Required API Keys

| Key | Where to Get | Required |
|-----|-------------|----------|
| `GROQ_API_KEY` | https://console.groq.com | ✅ Yes |
| `TMDB_API_KEY` | https://developer.themoviedb.org | ✅ Yes |
| `EMAILJS_*` | https://emailjs.com | Optional |

---

## 🗄️ Inspect the Database

```bash
sqlite3 users.db ".tables"
sqlite3 users.db "SELECT id, username, email FROM users;"
sqlite3 users.db "SELECT COUNT(*) FROM movies;"
sqlite3 users.db "SELECT u.username, r.movie_id, r.rating FROM ratings r JOIN users u ON r.user_id=u.id;"
```

---

## 📜 License

This project is for educational and personal use. TMDB data is subject to the [TMDB Terms of Use](https://www.themoviedb.org/documentation/api/terms-of-use).

---

<p align="center">Built with ❤️ using FastAPI + Groq + scikit-learn</p>
