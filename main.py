import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    
def main() -> None:
    setup_logging()
    
if __name__ == "__main__":
    main()