from models.trading import PairPosition

class Portfolio:
    
    def __init__(self, starting_capital: float = 10_000) -> None:
        self.starting_capital = starting_capital
        self.available_cash = starting_capital
        
        self.open_positions: dict[tuple[str, str], PairPosition] = dict()
        self.closed_positions: list[PairPosition] = []
        
    def has_position(self, ticker_y:str, ticker_x:str) -> bool:
        return (ticker_y, ticker_x) in self.open_positions
    
    def open_position(self, position: PairPosition) -> bool:
        
        return False
        