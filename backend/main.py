from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from auth import create_token, require_auth, verify_credentials
from predictor import forecast_budget, get_history, predict_current
from schemas import (
    BudgetRequest,
    BudgetResponse,
    HistoryResponse,
    LoginRequest,
    PredictionResponse,
)

app = FastAPI(title="Aurum AI", description="Real-Time UBS Gold Price Predictor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "Aurum AI"}


@app.post("/api/login")
def login(data: LoginRequest):
    if not verify_credentials(data.username, data.password):
        raise HTTPException(status_code=401, detail="Username atau password salah")
    return {"access_token": create_token(data.username), "token_type": "bearer"}


@app.get("/api/predict", response_model=PredictionResponse, dependencies=[Depends(require_auth)])
def predict():
    try:
        return predict_current()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history", response_model=HistoryResponse, dependencies=[Depends(require_auth)])
def history(days: int = Query(default=30, ge=7, le=365)):
    try:
        return {"data": get_history(days=days)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/budget", response_model=BudgetResponse, dependencies=[Depends(require_auth)])
def budget(req: BudgetRequest):
    try:
        return forecast_budget(
            budget_idr=req.budget_idr,
            weight_gram=req.weight_gram,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
