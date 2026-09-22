# Python ETL Pipeline & SQL Storage

A Python pipeline that fetches raw data from external APIs, cleans and formats the dataset, and saves it into a relational SQL database.

## Architecture
System data flow mapped in Diagram.io:
![Architecture Diagram](docs/architecture-diagram.png)

## What it does
- Fetches JSON data from HTTP endpoints using `requests`.
- Cleans missing values and formats dates using `pandas`.
- Handles batch insertion into PostgreSQL using `SQLAlchemy`.
- Logs execution errors and failed records.

## Project Structure
- `src/scraper.py` - Fetches raw data from API
- `src/transformer.py` - Cleaning and formatting logic
- `src/database.py` - SQL connection and batch insertion
- `sql/schema.sql` - Database table definitions

## How to run
1. Install dependencies:
   pip install -r requirements.txt
2. Run `sql/schema.sql` in your database client to create tables.
3. Run the pipeline:
   python src/main.py