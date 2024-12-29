import os
import configparser
from pathlib import Path

class Config:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self._load_config()

    def _load_config(self):
        config_dir = Path(__file__).parent.parent
        local_config = config_dir / 'config.local.ini'
        template_config = config_dir / 'config.template.ini'
        
        if local_config.exists():
            self.config.read(local_config)
        elif template_config.exists():
            self.config.read(template_config)
        else:
            raise FileNotFoundError("No configuration file found")

    @property
    def metronome_api_key(self) -> str:
        return self.config.get('metronome', 'api_key')

    @property
    def stripe_api_key(self) -> str:
        return self.config.get('stripe', 'api_key')