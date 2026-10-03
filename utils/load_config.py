import json
import logging

logger = logging.getLogger(__name__)
class Configuration:
    CONFIGURATION_FOLDER = "./config"
    
    def load_config(self, name:str):
        with open(f"{self.CONFIGURATION_FOLDER}/{name}") as file:
            self.config = json.load(file)
        
        logger.info(f"Loaded {name} configuration")
    
    def get_param(self, key:str):
        return self.config[key]