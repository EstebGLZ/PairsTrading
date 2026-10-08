from models.trading import PairPosition
import logging

logger = logging.getLogger(__name__)
class Portfolio:
    
    def __init__(self, starting_capital: float = 10_000) -> None:
        self.starting_capital = starting_capital
        self.available_cash = starting_capital
        
        self.open_positions: dict[tuple[str, str], PairPosition] = dict()
        self.closed_positions: list[PairPosition] = []
        
    def has_position(self, ticker_y:str, ticker_x:str) -> bool:
        return (ticker_y, ticker_x) in self.open_positions
    
    def open_position(self, position: PairPosition) -> bool:
        if(position.entry_value > self.available_cash):
            logger.debug(f"Position rejected: insufficient balance {position.entry_value} > {self.available_cash}")
            return False

        self.open_positions[position.pair] = position
        self.available_cash -= position.entry_value
        return True
    
    def close_position(self, position: PairPosition) -> bool:
        if not self.has_position(*position.pair):
            logger.debug(f"Position close rejected: position not found.")
            return False
        
        if not position.is_open:
            logger.debug(f"Position close rejected: position already closed.")
            return False
        
        self.open_positions.pop(position.pair)
        self.closed_positions.append(position)

        return True
        