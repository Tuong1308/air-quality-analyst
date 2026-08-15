@echo off
cd /d C:\AirQualityDataPJ\airquality-etl
call venv\Scripts\activate.bat
python -m src.main --lookback 7
