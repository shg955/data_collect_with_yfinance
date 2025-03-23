# Data Collection with yFinance

This project provides a Streamlit-based GUI for managing stock tickers and visualizing their data. It integrates with a PostgreSQL database to store ticker information and uses `yfinance` for data collection.

## Features

- Add, view, and delete stock tickers.
- Download collected data as CSV files.
- Display basic statistics and candlestick charts for stock data.

## Requirements

- Python 3.8+
- PostgreSQL database
- Streamlit
- Required Python libraries (see below)

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd data_collect_with_yfinance
   ```

2. Configure the PostgreSQL database:
   - Update the `.env` file

3. Run the `start.sh`:
   ```source start.sh```

## File Structure

- `data_GUI/streamlit_app.py`: Main Streamlit application.
- `data/`: Directory for storing downloaded CSV files.
- `.gitignore`: Specifies files and directories to ignore in version control.

## License

This project is licensed under the MIT License.