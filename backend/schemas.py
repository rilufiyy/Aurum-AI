from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class PredictionResponse(BaseModel):
    date: str
    predicted_price_idr: int
    actual_ubs_price_idr: int
    xauusd_live: float
    usdidr_live: float
    implied_spot_idr: float
    premium_pct: float
    prediction_error_idr: int
    prediction_error_pct: float
    ubs_price_date: str
    xauusd_date: str
    is_stale: bool


class HistoryPoint(BaseModel):
    date: str
    ubs_sell_idr: float
    xauusd: float
    usdidr: float
    implied_spot_idr: float


class HistoryResponse(BaseModel):
    data: list[HistoryPoint]


class BudgetRequest(BaseModel):
    budget_idr: float
    weight_gram: float = 1.0


class BudgetDayForecast(BaseModel):
    date: str
    predicted_price_idr: int
    units_affordable: float
    is_best_day: bool


class BudgetResponse(BaseModel):
    budget_idr: float
    weight_gram: float
    current_price_idr: int
    current_units_affordable: float
    forecast: list[BudgetDayForecast]
    recommendation: str


class NewsItem(BaseModel):
    title: str
    source: str
    published: str
    link: str
    sentiment: str
    score: int


class SentimentResponse(BaseModel):
    bullish_pct: float
    label: str
    news: list[NewsItem]
    fetched_at: str
