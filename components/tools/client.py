from datetime import datetime
import os
import re
from pathlib import Path

class Client:

    def __init__(self, config):
        self.config = config

        output_dir = self.config.get('client_config').get('output_dir')

        current_run_timestamp = datetime.now()
        current_run_timestamp = current_run_timestamp.strftime('%d-%m-%Y-%H-%M-%S')
        current_run_dir = f'{output_dir}/{current_run_timestamp}'

        self.output_dir = re.sub(r'\/+', '/', output_dir)
        self.current_run_dir = re.sub(r'\/+', '/', current_run_dir)

        if not os.path.exists(Path(output_dir)):
            os.makedirs(Path(output_dir))
            if not os.path.exists(Path(current_run_dir)):
                os.makedirs(Path(current_run_dir))

    def resolve_file(self, path, file):
        # Workaround for "space symbol" given in the Space name. Technically this is an error on the XS Advanced side
        path = re.sub(r'\s', '_', path)
        path = re.sub(r'\.', '_', path)
        
        path = f'{self.current_run_dir}/{path}'
        path = re.sub(r'\/+', '/', path)
        if not os.path.exists(Path(path)):
            os.makedirs(Path(path))
        file_path = f'{path}/{file}'
        file_path = re.sub(r'\/+', '/', file_path)
        return Path(file_path)

    def get_configured_logging_level(self):
        logging_level = self.config.get('client_config').get('logging_level')
        allowed_levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']
        return logging_level if logging_level in allowed_levels else 'NOTSET'

    def get_experimental_features_status(self):
        return self.config.get('controller_config').get('enable_experimental_features')
