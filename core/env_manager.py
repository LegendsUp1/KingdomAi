import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict

class EnvironmentManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        self.logger = logging.getLogger("EnvironmentManager")
        self._load_environment()
        self._verify_environment()
        
    def _load_environment(self):
        """Load environment variables from multiple sources"""
        # Load from .env file
        env_file = Path('.env')
        if env_file.exists():
            load_dotenv(env_file)
            self.logger.info("Loaded environment from .env file")
            
        # Verify critical variables
        self._required_vars = {
            'KINGDOM_ROOT': self._validate_directory,
            'KINGDOM_DATA_DIR': self._validate_directory,
            'KINGDOM_LOG_DIR': self._validate_directory,
            'KINGDOM_MODEL_DIR': self._validate_directory,
            'PYTHONPATH': self._validate_pythonpath,
            'CUDA_VISIBLE_DEVICES': str,
            'TF_ENABLE_ONEDNN_OPTS': str
        }
        
    def _validate_directory(self, path: str) -> bool:
        """Validate directory exists and is accessible"""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                path_obj.mkdir(parents=True)
                self.logger.info(f"Created directory: {path}")
            return True
        except Exception as e:
            self.logger.error(f"Directory validation failed for {path}: {e}")
            return False
            
    def _validate_pythonpath(self, path: str) -> bool:
        """Validate PYTHONPATH includes required directories"""
        paths = path.split(os.pathsep)
        kingdom_root = os.getenv('KINGDOM_ROOT', '')
        if kingdom_root not in paths:
            os.environ['PYTHONPATH'] = f"{kingdom_root}{os.pathsep}{path}"
            self.logger.info(f"Added {kingdom_root} to PYTHONPATH")
        return True
    
    def _verify_environment(self):
        """Verify all required environment variables"""
        missing_vars = []
        invalid_vars = []
        
        for var, validator in self._required_vars.items():
            value = os.getenv(var)
            if value is None:
                missing_vars.append(var)
            elif not validator(value):
                invalid_vars.append(var)
                
        if missing_vars or invalid_vars:
            self.logger.error(f"Missing variables: {missing_vars}")
            self.logger.error(f"Invalid variables: {invalid_vars}")
            raise EnvironmentError("Environment verification failed")
            
        self.logger.info("Environment verification completed successfully")
    
    def get_config(self) -> Dict[str, str]:
        """Get current environment configuration"""
        return {key: os.getenv(key) for key in self._required_vars.keys()}
    
    def update_variable(self, key: str, value: str):
        """Update environment variable with validation"""
        if key in self._required_vars:
            if self._required_vars[key](value):
                os.environ[key] = value
                self.logger.info(f"Updated {key} = {value}")
            else:
                raise ValueError(f"Invalid value for {key}")
        else:
            self.logger.warning(f"Updating non-standard variable: {key}")
            os.environ[key] = value
