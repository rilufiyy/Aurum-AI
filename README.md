# Aurum AI

Real-Time UBS Gold Price Predictor — prediksi harga emas UBS (PT Untung Bersama Sejahtera) per gram dalam Rupiah menggunakan machine learning.

## Cara Kerja

UBS tidak memiliki API publik. Aurum AI memetakan harga pasar real-time (XAU/USD + USD/IDR) ke harga jual UBS menggunakan model XGBoost yang dilatih pada data historis.

Model memprediksi **premium ratio** (`ubs_sell / implied_spot`) bukan harga absolut, sehingga pergerakan pasar dipisahkan dari markup UBS. Harga akhir = `predicted_ratio × live_implied_spot`.

## Fitur

- Prediksi harga UBS hari ini beserta error vs harga aktual
- Indikator staleness jika harga UBS belum diperbarui hari ini
- Riwayat harga 30 hari (UBS vs implied spot)
- Kalkulator budget — rekomendasi hari terbaik beli dalam 7 hari ke depan
- Login session dengan JWT

## Struktur Project

```
Aurum-AI/
├── data_ingestion.py       # Fase 1: ambil data historis XAU/USD, USD/IDR, UBS
├── train_model.py          # Fase 2: latih model XGBoost
├── requirements.txt
├── model/
│   ├── model.pkl
│   ├── feature_names.json
│   └── metrics.json
├── data/raw/
│   └── merged_features.csv
├── backend/
│   ├── main.py             # FastAPI app
│   ├── predictor.py        # Inferensi + fetch data live
│   ├── auth.py             # JWT login
│   ├── schemas.py          # Pydantic models
│   └── .env                # Kredensial (tidak di-commit)
└── frontend/
    ├── index.html
    ├── style.css
    ├── app.js
    ├── login.html
    ├── login.css
    └── login.js
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Ingest data historis

```bash
python data_ingestion.py
```

Output disimpan ke `data/raw/merged_features.csv`.

### 3. Latih model

```bash
python train_model.py
```

Output disimpan ke `model/`.

### 4. Konfigurasi kredensial

Edit `backend/.env`:

```env
APP_USERNAME=admin
APP_PASSWORD=ganti_password_ini
SECRET_KEY=string-acak-panjang-untuk-jwt
JWT_EXPIRE_MINUTES=1440
```

### 5. Jalankan backend

```bash
cd backend
uvicorn main:app --reload
```

Backend berjalan di `http://127.0.0.1:8000`.

### 6. Buka frontend

Buka `frontend/index.html` via Live Server (VS Code) atau:

```bash
cd frontend
python -m http.server 3000
```

Akses di `http://localhost:3000`.

## API Endpoints

| Method | Endpoint | Auth | Deskripsi |
|--------|----------|------|-----------|
| POST | `/api/login` | - | Login, dapat JWT token |
| GET | `/api/predict` | Bearer | Prediksi harga hari ini |
| GET | `/api/history?days=30` | Bearer | Riwayat harga |
| POST | `/api/budget` | Bearer | Forecast budget |

## Model

- **Algoritma**: XGBoost Regressor
- **Target**: `ubs_premium_ratio` = `ubs_sell_idr / implied_spot`
- **Fitur**: lag [1,2,3,5,7], rolling mean [5,10,20], pct_change, day_of_week, month
- **Validasi**: TimeSeriesSplit 5-fold
- **MAPE CV**: ~1.1%

## Data Sources

- **XAU/USD & USD/IDR**: [yfinance](https://github.com/ranaroussi/yfinance) (GC=F, USDIDR=X)
- **Harga UBS**: ubslifestyle.com WordPress AJAX API
