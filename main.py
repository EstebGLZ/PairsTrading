import logging
from data.fetcher import DataFetcher
from utils.load_config import Configuration
from data.feature import FeatureEngine
from engine.pair_engine import PairEngine
from engine.pair import PairSelectionConfig
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    
def main() -> None:
    setup_logging()
    
    config = Configuration()
    config.load_config("config.json")
    
    data = DataFetcher.fetch(config.get_param(key="stocks"), config.get_param("start"), config.get_param("end"))
    FeatureEngine.add_features(data)
    pairs = PairEngine.select_pairs(data, PairSelectionConfig(**config.get_param("pair_selection")))
    
    print(f"{pairs}")
if __name__ == "__main__":
    main()