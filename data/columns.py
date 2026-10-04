class Column:
    OPEN = "Open"
    HIGH = "High"
    LOW = "Low"
    CLOSE = "Close"
    VOLUME = "Volume"
    DATE = "Date"

class Feature:
    DAILY_RETURNS = "daily_returns"
    
PRICES_COLUMNS = [
    Column.OPEN,
    Column.HIGH,
    Column.LOW,
    Column.CLOSE,
    Column.VOLUME
]