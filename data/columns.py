class Column:
    OPEN = "Open"
    HIGH = "High"
    LOW = "Low"
    CLOSE = "Close"
    VOLUME = "Volume"
    DATE = "Date"

class Feature:
    LOG_PRICE = "log_price"
    DAILY_LOG_RETURNS = "daily_log_returns"
    OPTICS_CLUSTER = "optics_cluster"
    
PRICE_COLUMNS = [
    Column.OPEN,
    Column.HIGH,
    Column.LOW,
    Column.CLOSE,
    Column.VOLUME
]