# Falcon - Personal AI-powered Forex Signal Assistant

## Project Description
Falcon is a personal AI-powered Forex Signal Assistant.
This application will NEVER place trades and NEVER connects to a broker to execute trades. It ONLY analyzes the market and generates high-quality BUY, SELL, or WAIT signals.

Initially, Falcon supports ONLY:
- XAU/USD (Gold)
- GBP/USD

The user manually places trades on their preferred trading platform.

## Project Philosophy
"Accuracy first. Features second."

## Folder Explanation
- `backend/`: Python FastAPI backend.
- `mobile/`: Flutter mobile application.
- `docs/`: Project documentation.
- `database/`: Database schema, migrations, and seeds.
- `design/`: UI/UX designs and assets.

## Setup Instructions

### Prerequisites
- Python 3.10+
- Flutter SDK (>=3.0.0)
- PostgreSQL

### How to run backend
1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the development server:
   ```bash
   uvicorn main:app --reload
   ```

### How to run Flutter
1. Navigate to the `mobile/` directory:
   ```bash
   cd mobile
   ```
2. Get dependencies:
   ```bash
   flutter pub get
   ```
3. Run the app:
   ```bash
   flutter run
   ```
