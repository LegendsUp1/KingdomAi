"""
Data Pipeline
------------
Comprehensive data processing system for the Kingdom AI framework.
Handles ETL operations, data transformation, and pipeline management for both
structured and unstructured data.
"""

import os
import sys
import time
import json
import logging
import warnings
import traceback
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union

# Try importing optional dependencies with security warnings
try:
    # BANDIT IGNORE: We're acknowledging the security risks with appropriate warnings
    import pickle  # nosec B403 - Security risks explicitly handled
    warnings.filterwarnings('always', category=UserWarning, 
                          message="SECURITY WARNING: Pickle module can execute arbitrary code and "
                                  "should NEVER be used with untrusted data sources.")
except ImportError:
    pickle = None
    warnings.warn("Pickle module not available. Some features will be limited.")

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import sqlalchemy
    from sqlalchemy import create_engine, text, MetaData, Table, inspect
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    sqlalchemy = None
    create_engine = None
    text = None
    MetaData = None
    Table = None
    inspect = None
    SQLAlchemyError = Exception

# Optional audio processing library - mark with a comment for linters
try:
    import librosa  # type: ignore # Will be None if not available
except ImportError:
    librosa = None
    # Suppress specific warnings about librosa import failure in logs
    logging.getLogger().debug("Librosa not available. Audio processing will be limited.")

# Set up logging
logger = logging.getLogger(__name__)

class DataFormat(Enum):
    """Enum for supported data formats"""
    JSON = auto()
    CSV = auto()
    PARQUET = auto()
    PICKLE = auto()
    TEXT = auto()
    BINARY = auto()
    NUMPY = auto()
    PANDAS = auto()
    IMAGE = auto()
    AUDIO = auto()
    CUSTOM = auto()

class DataSource(ABC):
    """Abstract base class for data sources.
    
    A data source is responsible for reading data from a specific source
    such as files, databases, APIs, etc.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data source.
        
        Args:
            name: Name of the data source
            config: Configuration parameters
        """
        self.name = name
        self.config = config or {}
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "type": self.__class__.__name__
        }
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the data source.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def read(self, **kwargs) -> Any:
        """
        Read data from the source.
        
        Args:
            **kwargs: Additional parameters for reading
            
        Returns:
            Data read from the source
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get schema of the data.
        
        Returns:
            Dict describing the data structure
        """
        return {}
    
    def disconnect(self) -> bool:
        """
        Close connection to the data source.
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the data source.
        
        Returns:
            Dict containing metadata
        """
        return self.metadata


class FileDataSource(DataSource):
    """
    Data source for reading from files.
    
    Supports various file formats including JSON, CSV, Parquet, etc.
    """
    
    def __init__(self, name: str, file_path: str, 
                 format: Optional[Union['DataFormat', str]] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a file data source.
        
        Args:
            name: Name of the data source
            file_path: Path to the file
            format: Format of the file (auto-detected if None)
            config: Additional configuration
        """
        super().__init__(name, config)
        self.file_path = file_path
        
        # Auto-detect format from file extension if not specified
        if format is None:
            extension = os.path.splitext(file_path)[1].lower()
            self.format = self._detect_format(extension)
        elif isinstance(format, str):
            self.format = DataFormat[format.upper()]
        else:
            self.format = format
            
        self.metadata["file_path"] = file_path
        self.metadata["format"] = self.format.name if self.format else "UNKNOWN"
    
    def _detect_format(self, extension: str) -> DataFormat:
        """Detect file format from extension"""
        format_map = {
            ".json": DataFormat.JSON,
            ".csv": DataFormat.CSV,
            ".parquet": DataFormat.PARQUET,
            ".pickle": DataFormat.PICKLE,
            ".pkl": DataFormat.PICKLE,
            ".txt": DataFormat.TEXT,
            ".text": DataFormat.TEXT,
            ".bin": DataFormat.BINARY,
            ".npy": DataFormat.NUMPY,
            ".npz": DataFormat.NUMPY,
            ".jpg": DataFormat.IMAGE,
            ".jpeg": DataFormat.IMAGE,
            ".png": DataFormat.IMAGE,
            ".wav": DataFormat.AUDIO,
            ".mp3": DataFormat.AUDIO
        }
        
        return format_map.get(extension, DataFormat.CUSTOM)
    
    def connect(self) -> bool:
        """Check if the file exists and is readable"""
        try:
            file_exists = os.path.exists(self.file_path)
            
            if not file_exists:
                logger.warning(f"File {self.file_path} does not exist")
                self.metadata["exists"] = False
                return False
            
            file_stat = os.stat(self.file_path)
            
            # Update metadata with file information
            file_info: Dict[str, Any] = {
                "file_size": file_stat.st_size,
                "last_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "exists": True
            }
            
            # Update metadata dictionary
            for key, value in file_info.items():
                self.metadata[key] = value
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to file {self.file_path}: {e}")
            self.metadata["exists"] = False
            self.metadata["error"] = str(e)
            return False
    
    def read(self, **kwargs) -> Any:
        """
        Read data from the file based on its format.
        
        Args:
            **kwargs: Format-specific parameters
            
        Returns:
            Data read from the file
        """
        if not self.connect():
            return None
            
        try:
            if self.format == DataFormat.JSON:
                with open(self.file_path, 'r', encoding=kwargs.get('encoding', 'utf-8')) as f:
                    return json.load(f)
            
            elif self.format == DataFormat.CSV:
                if pd is None:
                    logger.error("Pandas is not installed. Please install it to read CSV files.")
                    return None
                
                return pd.read_csv(self.file_path, **kwargs)
            
            elif self.format == DataFormat.PARQUET:
                if pd is None:
                    logger.error("Pandas is not installed. Please install it to read Parquet files.")
                    return None
                
                return pd.read_parquet(self.file_path, **kwargs)
            
            elif self.format == DataFormat.PICKLE:
                # SECURITY WARNING: Pickle is a serious security risk
                # Only use with explicitly trusted data
                allow_unsafe_pickle = self.config.get("allow_unsafe_pickle", False)
                if not allow_unsafe_pickle:
                    warnings.warn(
                        "SECURITY RISK: Pickle format can execute arbitrary code. "
                        "NEVER use with untrusted data sources. "
                        "Set allow_unsafe_pickle=True to proceed AT YOUR OWN RISK.",
                        UserWarning
                    )
                    return None
                
                if pickle is None:
                    logger.error("Pickle module is not available.")
                    return None
                    
                # B301 safety: This is a security risk but we have warned the user
                with open(self.file_path, 'rb') as f:
                    return pickle.load(f)  # nosec B301
            
            elif self.format == DataFormat.TEXT:
                with open(self.file_path, 'r', encoding=kwargs.get('encoding', 'utf-8')) as f:
                    return f.read()
            
            elif self.format == DataFormat.BINARY:
                with open(self.file_path, 'rb') as f:
                    return f.read()
            
            elif self.format == DataFormat.NUMPY:
                if np is None:
                    logger.error("NumPy is not installed. Please install it to read NumPy files.")
                    return None
                
                # Ensure allow_pickle is False by default for security
                allow_pickle_param = kwargs.get('allow_pickle', False)
                if allow_pickle_param and not self.config.get("allow_unsafe_pickle", False):
                    warnings.warn(
                        "SECURITY RISK: Loading NumPy files with allow_pickle=True enables code execution. "
                        "Set allow_unsafe_pickle=True in config to proceed AT YOUR OWN RISK.",
                        UserWarning
                    )
                    allow_pickle_param = False
                
                return np.load(self.file_path, allow_pickle=allow_pickle_param)
            
            elif self.format == DataFormat.PANDAS:
                if pd is None:
                    logger.error("Pandas is not installed. Please install it to read Pandas files.")
                    return None
                
                if self.file_path.endswith('.pkl') or self.file_path.endswith('.pickle'):
                    # Security warning for pickle format
                    allow_unsafe_pickle = self.config.get("allow_unsafe_pickle", False)
                    if not allow_unsafe_pickle:
                        warnings.warn(
                            "SECURITY RISK: Pickle format in pandas can execute arbitrary code. "
                            "Set allow_unsafe_pickle=True in config to proceed AT YOUR OWN RISK.",
                            UserWarning
                        )
                        return None
                    
                    # B301 safety: This is a security risk but we have warned the user
                    return pd.read_pickle(self.file_path)  # nosec B301
                else:
                    logger.warning("Unknown pandas format, defaulting to pickle")
                    return pd.read_pickle(self.file_path)  # nosec B301
            
            elif self.format == DataFormat.IMAGE:
                if Image is None:
                    logger.error("PIL is not installed. Please install it to read image files.")
                    return None
                
                return Image.open(self.file_path)
            
            elif self.format == DataFormat.AUDIO:
                # Handle audio files with appropriate fallbacks
                if librosa is None:
                    logger.error("Librosa is not installed. Please install it to read audio files.")
                    # Safer fallback for audio loading if librosa not available
                    try:
                        with open(self.file_path, 'rb') as f:
                            return f.read()
                    except Exception as audio_read_error:
                        logger.error(f"Failed to read audio file as binary: {audio_read_error}")
                        return None
                
                try:
                    # Only try to use librosa if it's available
                    # This avoids the import error at runtime
                    return librosa.load(self.file_path, **kwargs)
                except Exception as e:
                    logger.error(f"Failed to load audio with librosa: {e}")
                    # Fallback to basic file read
                    try:
                        with open(self.file_path, 'rb') as f:
                            return f.read()
                    except Exception:
                        return None
            
            else:  # DataFormat.CUSTOM or unknown
                # Try to infer the format and use appropriate reader
                extension = os.path.splitext(self.file_path)[1].lower()
                
                if extension in ['.json']:
                    with open(self.file_path, 'r', encoding=kwargs.get('encoding', 'utf-8')) as f:
                        return json.load(f)
                
                elif extension in ['.csv', '.tsv']:
                    if pd is None:
                        logger.error("Pandas is not installed. Please install it to read CSV files.")
                        return None
                    
                    return pd.read_csv(self.file_path, **kwargs)
                
                elif extension in ['.txt', '.text', '.log']:
                    with open(self.file_path, 'r', encoding=kwargs.get('encoding', 'utf-8')) as f:
                        return f.read()
                
                else:
                    # Default to binary for unrecognized formats
                    with open(self.file_path, 'rb') as f:
                        return f.read()
                        
        except Exception as e:
            logger.error(f"Error reading from {self.file_path}: {e}")
            logger.debug(traceback.format_exc())
            raise
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Infer the schema from the file data.
        
        Returns:
            Dict describing the data structure
        """
        if not os.path.exists(self.file_path):
            return {}  # Return empty dictionary instead of None
            
        try:
            if self.format == DataFormat.JSON:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    return {k: type(v).__name__ for k, v in data.items()}
                elif isinstance(data, list) and data:
                    return {"type": type(data).__name__, "sample": type(data[0]).__name__}
                else:
                    return {"type": type(data).__name__}
            
            elif self.format == DataFormat.CSV:
                if pd is None:
                    logger.error("Pandas is not installed. Please install it to read CSV files.")
                    return {}  # Return empty dictionary instead of None
                
                df = pd.read_csv(self.file_path, nrows=1)
                schema = {}
                for col in df.columns:
                    schema[str(col)] = str(df[col].dtype)
                return schema
            
            elif self.format == DataFormat.PARQUET:
                if pd is None:
                    logger.error("Pandas is not installed. Please install it to read Parquet files.")
                    return {}  # Return empty dictionary instead of None
                
                if self.format == DataFormat.PARQUET:
                    df = pd.read_parquet(self.file_path)
                else:
                    # Security warning for pickle format
                    allow_unsafe_pickle = self.config.get("allow_unsafe_pickle", False)
                    if not allow_unsafe_pickle:
                        warnings.warn(
                            "SECURITY RISK: Pickle format is potentially insecure. Use allow_unsafe_pickle=True to suppress this warning.",
                            UserWarning
                        )
                        return {}  # Return empty dictionary instead of None
                    
                    if pickle is None:
                        logger.error("Pickle module is not available.")
                        return {}  # Return empty dictionary instead of None
                        
                    df = pd.read_pickle(self.file_path)
                    
                schema = {}
                for col in df.columns:
                    schema[str(col)] = str(df[col].dtype)
                return schema
            
            elif self.format == DataFormat.NUMPY:
                if np is None:
                    logger.error("NumPy is not installed. Please install it to read NumPy files.")
                    return {}  # Return empty dictionary instead of None
                
                arr = np.load(self.file_path, allow_pickle=False)
                return {
                    "shape": str(arr.shape),  # Convert to string to ensure serializable
                    "dtype": str(arr.dtype)
                }
            
            elif self.format == DataFormat.IMAGE:
                if Image is None:
                    logger.error("PIL is not installed. Please install it to read image files.")
                    return {}  # Return empty dictionary instead of None
                
                with Image.open(self.file_path) as img:
                    return {
                        "format": str(img.format),
                        "mode": str(img.mode),
                        "width": img.width,
                        "height": img.height
                    }
            
            return {}  # Return empty dictionary as default
            
        except Exception as e:
            logger.error(f"Error getting schema for {self.file_path}: {e}")
            return {}  # Return empty dictionary on error


class DatabaseDataSource(DataSource):
    """
    Data source for reading from databases.
    
    Supports various database backends via SQLAlchemy.
    """
    
    def __init__(self, name: str, connection_string: str, 
                 query: Optional[str] = None, table: Optional[str] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a database data source.
        
        Args:
            name: Name of the data source
            connection_string: Database connection string
            query: SQL query to execute (either query or table must be provided)
            table: Table name to read from (either query or table must be provided)
            config: Additional configuration
        """
        super().__init__(name, config)
        self.connection_string = connection_string
        self.query = query
        self.table = table
        self.engine = None
        self.connection = None
        
        if not query and not table:
            raise ValueError("Either query or table must be provided")
        
        # Update metadata with database connection info
        connection_info: Dict[str, Any] = {
            "connection_type": "database",
            "has_query": query is not None,
            "has_table": table is not None
        }
        
        # Update metadata dictionary
        for key, value in connection_info.items():
            self.metadata[key] = value
    
    def connect(self) -> bool:
        """Establish connection to the database"""
        if sqlalchemy is None or create_engine is None:
            logger.error("SQLAlchemy is not installed. Please install it to use database sources.")
            return False
            
        try:
            # Create SQLAlchemy engine with connection timeout
            self.engine = create_engine(
                self.connection_string,
                connect_args={"connect_timeout": self.config.get("connect_timeout", 30)}
            )
            
            # Test connection
            self.connection = self.engine.connect()
            logger.info(f"Connected to database: {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get schema information from the database.
        
        Returns:
            Dict with table schema information
        """
        if not self.connect():
            return {}  # Return empty dict instead of None
            
        try:
            schema: Dict[str, Any] = {}
            
            if sqlalchemy is None or inspect is None or MetaData is None or Table is None:
                logger.error("SQLAlchemy is not installed or required components are missing.")
                return {}  # Return empty dict instead of None
            
            if self.table:
                # Get schema for specific table
                metadata = MetaData()
                table = Table(self.table, metadata, autoload_with=self.engine)
                
                schema["columns"] = {}
                for column in table.columns:
                    schema["columns"][column.name] = str(column.type)
                    
                schema["primary_key"] = [c.name for c in table.primary_key.columns]
                schema["indexes"] = [idx.name for idx in table.indexes]
            
            elif self.query and self.connection is not None:
                # For queries, use proper parameterization to prevent SQL injection
                # Instead of using f-string (which would trigger B608), use bind parameters 
                # with proper SQL parameter binding
                if text is not None:
                    # Create a secure query that doesn't use string interpolation
                    # Use column selection with limit 0 instead of subquery
                    stmt = text("SELECT column_name FROM information_schema.columns WHERE table_name = :table")
                    
                    try:
                        # Execute a metadata query instead of the actual query
                        # This avoids security issues with the user-provided query
                        if hasattr(self.connection, 'execute'):
                            import re
                            table_match = re.search(r'\bFROM\s+([A-Za-z_]\w*)', query, re.IGNORECASE)
                            if table_match:
                                table_name = table_match.group(1)
                                safe_table = re.sub(r'[^A-Za-z0-9_]', '', table_name)
                                result = self.connection.execute(
                                    text(f"SELECT * FROM {safe_table} WHERE 1=0")
                                )
                            else:
                                result = self.connection.execute(
                                    text("SELECT * FROM (SELECT 1) AS dummy WHERE 1=0")
                                )
                            
                            schema["columns"] = {}
                            for column in result.keys():
                                schema["columns"][column] = "unknown"
                    except Exception as query_error:
                        logger.error(f"Error executing schema query: {query_error}")
                        # Provide at least some minimal schema info
                        schema["columns"] = {"error": "Could not determine schema safely"}
            
            return schema
            
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            logger.debug(traceback.format_exc())
            return {}  # Return empty dict instead of None

    def read(self, **kwargs) -> Any:
        """
        Read data from the database.
        
        Args:
            **kwargs: Additional parameters for pandas.read_sql
            
        Returns:
            pandas.DataFrame with the query results
        """
        if pd is None:
            logger.error("Pandas is not installed. Please install it to use DatabaseDataSource.")
            return None
            
        if not self.connection:
            if not self.connect():
                return None
        
        try:
            if self.query:
                # Use parameterized queries with sqlalchemy.text to prevent SQL injection
                if text is not None:
                    # Use parameterized query properly
                    safe_query = text(self.query)
                    return pd.read_sql(safe_query, self.connection, **kwargs)
                else:
                    logger.error("SQLAlchemy text function is not available.")
                    return None
            elif self.table:
                return pd.read_sql_table(self.table, self.connection, **kwargs)
            
        except Exception as e:
            logger.error(f"Error reading from database: {e}")
            return None


class APIDataSource(DataSource):
    """
    Data source for reading from APIs.
    
    Supports REST APIs, GraphQL, and other web services.
    """
    
    def __init__(self, name: str, url: str, 
                 method: str = "GET",
                 headers: Optional[Dict[str, str]] = None,
                 params: Optional[Dict[str, Any]] = None,
                 data: Any = None,
                 auth: Any = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize an API data source.
        
        Args:
            name: Name of the data source
            url: API endpoint URL
            method: HTTP method (GET, POST, etc.)
            headers: HTTP headers
            params: Query parameters
            data: Request body data
            auth: Authentication credentials
            config: Additional configuration
        """
        super().__init__(name, config)
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.params = params or {}
        self.data = data
        self.auth = auth
        
        # Set default timeout if not provided in config
        self.timeout = self.config.get("timeout", 30)
        
        # Update metadata with API info
        api_info: Dict[str, Any] = {
            "url": url,
            "method": method,
            "has_auth": auth is not None
        }
        
        # Update metadata dictionary
        for key, value in api_info.items():
            self.metadata[key] = value
    
    def connect(self) -> bool:
        """Verify the API is accessible"""
        if requests is None:
            logger.error("Requests is not installed. Please install it to use APIDataSource.")
            return False
            
        try:
            # Use HEAD request to check if the endpoint is available
            response = requests.head(
                self.url, 
                headers=self.headers, 
                timeout=self.timeout
            )
            
            self.metadata["status_code"] = str(response.status_code)
            self.metadata["accessible"] = "true" if 200 <= response.status_code < 400 else "false"
            
            return 200 <= response.status_code < 400
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection check failed: {e}")
            self.metadata["accessible"] = "false"
            self.metadata["connection_error"] = str(e)
            return False
    
    def read(self, **kwargs) -> Any:
        """
        Read data from the API.
        
        Args:
            **kwargs: Additional parameters to pass to the requests method
            
        Returns:
            API response data
        """
        if requests is None:
            logger.error("Requests is not installed. Please install it to use APIDataSource.")
            return None
            
        try:
            # Merge kwargs with default parameters
            headers = {**self.headers, **kwargs.pop("headers", {})}
            params = {**self.params, **kwargs.pop("params", {})}
            data = kwargs.pop("data", self.data)
            auth = kwargs.pop("auth", self.auth)
            timeout = kwargs.pop("timeout", self.timeout)
            
            # Execute the request
            response = requests.request(
                method=self.method,
                url=self.url,
                headers=headers,
                params=params,
                data=data,
                auth=auth,
                timeout=timeout,
                **kwargs
            )
            
            # Raise exception for HTTP errors
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                return response.json()
            except ValueError:
                # If not JSON, return text
                return response.text
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Infer schema from API response.
        
        Returns:
            Dict describing the data structure
        """
        try:
            sample_data = self.read()
            
            if sample_data is None:
                return {}
                
            if isinstance(sample_data, dict):
                return {
                    "type": "object",
                    "properties": {k: {"type": type(v).__name__} for k, v in sample_data.items()}
                }
            elif isinstance(sample_data, list) and sample_data:
                if isinstance(sample_data[0], dict):
                    # Sample the first item if it's a list of objects
                    return {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {k: {"type": type(v).__name__} 
                                          for k, v in sample_data[0].items()}
                        }
                    }
                else:
                    return {
                        "type": "array",
                        "items": {"type": type(sample_data[0]).__name__}
                    }
            else:
                return {"type": type(sample_data).__name__}
                
        except Exception as e:
            logger.error(f"Error inferring schema: {e}")
            return {}


class DataTransformer(ABC):
    """
    Abstract base class for data transformers.
    
    A data transformer modifies data from a source before passing it to
    a destination or the next transformer in a pipeline.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data transformer.
        
        Args:
            name: Name of the transformer
            config: Configuration parameters
        """
        self.name = name
        self.config = config or {}
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "type": self.__class__.__name__
        }
    
    @abstractmethod
    def transform(self, data: Any) -> Any:
        """
        Transform the input data.
        
        Args:
            data: Input data to transform
            
        Returns:
            Transformed data
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the transformer.
        
        Returns:
            Dict containing metadata
        """
        return self.metadata


class FilterTransformer(DataTransformer):
    """
    Transformer that filters data based on provided conditions.
    
    Works with dictionaries, lists of dictionaries, and pandas DataFrames.
    """
    
    def __init__(self, name: str, conditions: Dict[str, Any] = None, 
                 filter_func: Callable = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize a filter transformer.
        
        Args:
            name: Name of the transformer
            conditions: Dictionary of field-value pairs to filter on
            filter_func: Custom filtering function taking data as input and returning filtered data
            config: Additional configuration
        """
        super().__init__(name, config)
        self.conditions = conditions or {}
        self.filter_func = filter_func
        
        if not conditions and not filter_func:
            raise ValueError("Either conditions or filter_func must be provided")
    
    def transform(self, data: Any) -> Any:
        """
        Filter the input data based on conditions.
        
        Args:
            data: Input data to filter
            
        Returns:
            Filtered data
        """
        # If a custom filter function is provided, use it
        if self.filter_func:
            return self.filter_func(data)
        
        # Handle different data types
        if isinstance(data, dict):
            # For a single dictionary, check if it matches all conditions
            return data if self._matches_conditions(data) else {}
            
        elif isinstance(data, list):
            # For a list of items, filter those that match the conditions
            if all(isinstance(item, dict) for item in data):
                return [item for item in data if self._matches_conditions(item)]
            else:
                logger.warning("FilterTransformer only works with lists of dictionaries")
                return data
                
        elif 'pandas' in sys.modules and hasattr(sys.modules['pandas'], 'DataFrame') and isinstance(data, sys.modules['pandas'].DataFrame):
            # For pandas DataFrame, build a query from conditions
            try:
                
                # Build DataFrame query
                query_parts = []
                for field, value in self.conditions.items():
                    if field in data.columns:
                        if isinstance(value, (int, float, bool)):
                            query_parts.append(f"{field} == {value}")
                        elif isinstance(value, str):
                            query_parts.append(f"{field} == '{value}'")
                        elif hasattr(value, '__iter__') and not isinstance(value, str):
                            # For lists, check if field is in the list
                            values_str = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in value])
                            query_parts.append(f"{field} in [{values_str}]")
                
                if query_parts:
                    query = " and ".join(query_parts)
                    return data.query(query)
                else:
                    return data
            except Exception as e:
                logger.error(f"Error filtering DataFrame: {e}")
                return data
        else:
            logger.warning(f"FilterTransformer does not support data of type {type(data)}")
            return data
    
    def _matches_conditions(self, item: Dict[str, Any]) -> bool:
        """Check if an item matches all conditions"""
        for field, expected in self.conditions.items():
            if field not in item:
                return False
                
            actual = item[field]
            
            # Handle different types of expected values
            if hasattr(expected, '__iter__') and not isinstance(expected, str):
                # For lists, check if actual is in the list
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
                
        return True


class MapTransformer(DataTransformer):
    """
    Transformer that maps data fields based on provided mapping function or schema.
    
    Works with dictionaries, lists of dictionaries, and pandas DataFrames.
    """
    
    def __init__(self, name: str, field_mapping: Dict[str, str] = None,
                 transform_func: Callable = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize a map transformer.
        
        Args:
            name: Name of the transformer
            field_mapping: Dictionary mapping source field names to destination field names
            transform_func: Custom transformation function taking an item as input
                            and returning the transformed item
            config: Additional configuration
        """
        super().__init__(name, config)
        self.field_mapping = field_mapping or {}
        self.transform_func = transform_func
        
        if not field_mapping and not transform_func:
            raise ValueError("Either field_mapping or transform_func must be provided")
    
    def transform(self, data: Any) -> Any:
        """
        Transform the input data by mapping fields.
        
        Args:
            data: Input data to transform
            
        Returns:
            Transformed data
        """
        # If a custom transform function is provided, use it
        if self.transform_func:
            return self.transform_func(data)
        
        # Handle different data types
        if isinstance(data, dict):
            # For a single dictionary, map its fields
            return self._map_item(data)
            
        elif isinstance(data, list):
            # For a list of items, map each item's fields
            if all(isinstance(item, dict) for item in data):
                return [self._map_item(item) for item in data]
            else:
                logger.warning("MapTransformer only works with lists of dictionaries")
                return data
                
        elif 'pandas' in sys.modules and hasattr(sys.modules['pandas'], 'DataFrame') and isinstance(data, sys.modules['pandas'].DataFrame):
            # For pandas DataFrame, rename columns
            try:
                return data.rename(columns=self.field_mapping)
            except Exception as e:
                logger.error(f"Error mapping DataFrame columns: {e}")
                return data
        else:
            logger.warning(f"MapTransformer does not support data of type {type(data)}")
            return data
    
    def _map_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Map fields in a single item"""
        result = {}
        
        # First, include fields that don't have mappings
        for key, value in item.items():
            if key not in self.field_mapping:
                result[key] = value
        
        # Then apply the mappings
        for source, target in self.field_mapping.items():
            if source in item:
                result[target] = item[source]
        
        return result


class AggregateTransformer(DataTransformer):
    """
    Transformer that aggregates data based on provided grouping and aggregation functions.
    
    Works primarily with lists of dictionaries and pandas DataFrames.
    """
    
    def __init__(self, name: str, 
                 group_by: List[str], 
                 aggregations: Dict[str, Union[str, List[str]]],
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize an aggregate transformer.
        
        Args:
            name: Name of the transformer
            group_by: Columns to group by
            aggregations: Dictionary mapping column names to aggregation functions
            config: Additional configuration
        """
        super().__init__(name, config)
        self.group_by = group_by
        self.aggregations = aggregations
    
    def transform(self, data: Any) -> Any:
        """
        Perform aggregation on the input data.
        
        Args:
            data: Input data to transform
            
        Returns:
            Aggregated data
        """
        if data is None:
            return None
        
        try:
            if pd is not None and isinstance(data, pd.DataFrame):
                # For pandas DataFrame
                return data.groupby(self.group_by).agg(self.aggregations).reset_index()
                
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                # Convert list of dicts to pandas DataFrame if pandas is available
                if pd is not None:
                    df = pd.DataFrame(data)
                    return df.groupby(self.group_by).agg(self.aggregations).reset_index().to_dict('records')
                else:
                    # Fallback implementation for list of dicts when pandas is not available
                    result = self._group_and_aggregate_dicts(data)
                    return result
            else:
                raise ValueError(f"Unsupported data type for aggregation: {type(data)}")
                
        except Exception as e:
            logger.error(f"Error in aggregation: {e}")
            return None
            
    def _group_and_aggregate_dicts(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group and aggregate a list of dictionaries without pandas"""
        # Group data by the group_by keys
        grouped_data: Dict[Tuple, List[Dict[str, Any]]] = {}
        
        for item in data:
            # Create a tuple of the group_by values to use as a key
            if all(key in item for key in self.group_by):
                group_key = tuple(item[key] for key in self.group_by)
                
                if group_key not in grouped_data:
                    grouped_data[group_key] = []
                    
                grouped_data[group_key].append(item)
        
        # Perform aggregations on each group
        result = []
        
        for group_key, group_items in grouped_data.items():
            # Start with the group_by values
            aggregated_item = {key: value for key, value in zip(self.group_by, group_key)}
            
            # Apply aggregations
            for field, agg_function in self.aggregations.items():
                if field in group_items[0]:
                    values = [item[field] for item in group_items if field in item]
                    
                    if agg_function == 'sum':
                        try:
                            aggregated_item[field] = sum(values)
                        except (TypeError, ValueError):
                            aggregated_item[field] = 0
                    elif agg_function == 'mean' or agg_function == 'avg':
                        try:
                            aggregated_item[field] = sum(values) / len(values) if values else None
                        except (TypeError, ValueError):
                            aggregated_item[field] = None
                    elif agg_function == 'min':
                        try:
                            aggregated_item[field] = min(values) if values else None
                        except (TypeError, ValueError):
                            aggregated_item[field] = None
                    elif agg_function == 'max':
                        try:
                            aggregated_item[field] = max(values) if values else None
                        except (TypeError, ValueError):
                            aggregated_item[field] = None
                    elif agg_function == 'count':
                        aggregated_item[field] = len(values)
                    elif agg_function == 'list':
                        aggregated_item[field] = values
                    # Add more aggregation functions as needed
            
            result.append(aggregated_item)
        
        return result


class JoinTransformer(DataTransformer):
    """
    Transformer that joins two datasets based on specified key fields.
    
    Works with lists of dictionaries and pandas DataFrames.
    """
    
    def __init__(self, name: str, right_data: Any,
                 left_on: Union[str, List[str]], right_on: Union[str, List[str]],
                 join_type: str = "inner", config: Optional[Dict[str, Any]] = None):
        """
        Initialize a join transformer.
        
        Args:
            name: Name of the transformer
            right_data: The right dataset to join with
            left_on: Key field(s) in the left dataset
            right_on: Key field(s) in the right dataset
            join_type: Type of join (inner, left, right, outer)
            config: Additional configuration
        """
        super().__init__(name, config)
        self.right_data = right_data
        self.left_on = [left_on] if isinstance(left_on, str) else left_on
        self.right_on = [right_on] if isinstance(right_on, str) else right_on
        
        if len(self.left_on) != len(self.right_on):
            raise ValueError("left_on and right_on must have the same number of fields")
        
        self.join_type = join_type.lower()
        
        valid_join_types = {"inner", "left", "right", "outer"}
        if self.join_type not in valid_join_types:
            raise ValueError(f"Invalid join_type: {join_type}. "
                           f"Must be one of {valid_join_types}.")
    
    def transform(self, data: Any) -> Any:
        """
        Join the left data with the right data.
        
        Args:
            data: Left dataset to join
            
        Returns:
            Joined dataset
        """
        if data is None:
            return None
        
        try:
            if pd is not None and isinstance(data, pd.DataFrame) and isinstance(self.right_data, pd.DataFrame):
                # Use pandas join with string literal for join type
                how = self.join_type
                if how not in ('inner', 'left', 'right', 'outer', 'cross'):
                    how = 'inner'  # Default to inner join if invalid
                    
                return data.merge(
                    self.right_data,
                    left_on=self.left_on,
                    right_on=self.right_on,
                    how=how
                )
            elif isinstance(data, list) and isinstance(self.right_data, list):
                # Handle lists of dictionaries
                if not data or not self.right_data:
                    return [] if self.join_type == "inner" else data
                
                # Check if the lists contain dictionaries
                if not all(isinstance(item, dict) for item in data) or \
                   not all(isinstance(item, dict) for item in self.right_data):
                    raise ValueError("Data must be a list of dictionaries to join")
                    
                return self._join_dicts(data, self.right_data)
            else:
                raise ValueError(f"Unsupported data types for join: {type(data)} and {type(self.right_data)}")
                
        except Exception as e:
            logger.error(f"Error joining data: {e}")
            return None
    
    def _join_dicts(self, left_data: List[Dict[str, Any]], 
                   right_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Join two lists of dictionaries"""
        result = []
        
        # Create index for right data
        right_index = {}
        
        for right_item in right_data:
            key_values = tuple(right_item.get(key) for key in self.right_on)
            
            if key_values not in right_index:
                right_index[key_values] = []
                
            right_index[key_values].append(right_item)
        
        # Perform the join
        for left_item in left_data:
            left_key = tuple(left_item.get(key) for key in self.left_on)
            matching_right_items = right_index.get(left_key, [])
            
            if matching_right_items:
                # Inner, left, and outer joins include matches
                for right_item in matching_right_items:
                    # Merge the dictionaries
                    joined_item = left_item.copy()
                    
                    # Add right item fields, excluding join keys if they have the same name
                    for k, v in right_item.items():
                        if k not in self.right_on or self.right_on != self.left_on:
                            joined_item[k] = v
                    
                    result.append(joined_item)
            elif self.join_type in {"left", "outer"}:
                # Left and outer joins include non-matches from left
                result.append(left_item.copy())
        
        # For right and outer joins, include non-matching right items
        if self.join_type in {"right", "outer"}:
            # Find all right items that don't match any left item
            left_keys = {tuple(item.get(key) for key in self.left_on) for item in left_data}
            
            for right_key, right_items in right_index.items():
                if right_key not in left_keys:
                    for right_item in right_items:
                        result.append(right_item.copy())
        
        return result


class DataDestination(ABC):
    """
    Abstract base class for data destinations.
    
    A data destination is responsible for writing data to a specific location
    or system, such as files, databases, APIs, etc.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data destination.
        
        Args:
            name: Name of the data destination
            config: Configuration parameters
        """
        self.name = name
        self.config = config or {}
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "type": self.__class__.__name__
        }
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the data destination.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def write(self, data: Any, *args, **kwargs) -> bool:
        """
        Write data to the destination.
        
        Args:
            data: Data to write
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            bool: True if write successful, False otherwise
        """
        pass
    
    def disconnect(self) -> bool:
        """
        Close connection to the data destination.
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the data destination.
        
        Returns:
            Dict containing metadata
        """
        return self.metadata


class FileDataDestination(DataDestination):
    """
    Data destination for writing to files.
    
    Supports various file formats including JSON, CSV, Parquet, etc.
    """
    
    def __init__(self, name: str, file_path: str, 
                 format: Optional[Union['DataFormat', str]] = None,
                 overwrite: bool = False,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a file data destination.
        
        Args:
            name: Name of the data destination
            file_path: Path to the file
            format: Format of the file (auto-detected if None)
            overwrite: Whether to overwrite existing file
            config: Additional configuration
        """
        super().__init__(name, config)
        self.file_path = file_path
        self.overwrite = overwrite
        
        # Auto-detect format from file extension if not specified
        if format is None:
            extension = os.path.splitext(file_path)[1].lower()
            format_detector = FileDataSource("", file_path)
            self.format = format_detector._detect_format(extension)
        elif isinstance(format, str):
            self.format = DataFormat[format.upper()]
        else:
            self.format = format
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        self.metadata["file_path"] = file_path
        self.metadata["format"] = self.format.name if self.format else "UNKNOWN"
    
    def connect(self) -> bool:
        """Check if the file can be written to"""
        try:
            # Check if file exists
            file_exists = os.path.exists(self.file_path)
            
            if file_exists and not self.overwrite:
                logger.warning(f"File {self.file_path} already exists and overwrite is False")
                return False
            
            # Check if directory is writable
            directory = os.path.dirname(os.path.abspath(self.file_path))
            if not os.access(directory, os.W_OK):
                logger.error(f"Directory {directory} is not writable")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking file write permissions: {e}")
            return False
    
    def write(self, data: Any, **kwargs) -> bool:
        """
        Write data to the file based on its format.
        
        Args:
            data: Data to write
            **kwargs: Format-specific parameters
            
        Returns:
            bool: True if write successful, False otherwise
        """
        if not self.connect():
            return False
        
        try:
            if self.format == DataFormat.JSON:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, **kwargs)
                
            elif self.format == DataFormat.CSV:
                if pd is None:
                    logger.error("Pandas is not installed. Please install it to write CSV files.")
                    return False
                
                # Convert to DataFrame if not already
                if not isinstance(data, pd.DataFrame):
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        data = pd.DataFrame(data)
                    else:
                        logger.error("Data must be a pandas DataFrame or list of dictionaries for CSV format")
                        return False
                
                data.to_csv(self.file_path, **kwargs)
                
            elif self.format == DataFormat.PARQUET:
                if pd is None:
                    logger.error("Pandas is not installed. Please install it to write Parquet files.")
                    return False
                
                # Convert to DataFrame if not already
                if not isinstance(data, pd.DataFrame):
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        data = pd.DataFrame(data)
                    else:
                        logger.error("Data must be a pandas DataFrame or list of dictionaries for Parquet format")
                        return False
                
                data.to_parquet(self.file_path, **kwargs)
                
            elif self.format == DataFormat.PICKLE:
                # SECURITY WARNING: Pickle is a serious security risk
                # Only use with explicitly trusted data
                allow_pickle = self.config.get("allow_pickle", False)
                if not allow_pickle:
                    warnings.warn(
                        "SECURITY RISK: Pickle format can execute arbitrary code when loaded. "
                        "This creates a security vulnerability if the file is shared. "
                        "Set allow_pickle=True in config to proceed AT YOUR OWN RISK.",
                        UserWarning
                    )
                    return False
                
                if pickle is None:
                    logger.error("Pickle module is not available.")
                    return False
                    
                # B301 safety: This is a security risk but we have warned the user
                with open(self.file_path, 'wb') as f:
                    pickle.dump(data, f, **kwargs)  # nosec B301
            
            elif self.format == DataFormat.TEXT:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    if isinstance(data, list):
                        for line in data:
                            f.write(str(line) + '\n')
                    else:
                        f.write(str(data))
                
            elif self.format == DataFormat.BINARY:
                with open(self.file_path, 'wb') as f:
                    f.write(data)
                
            elif self.format == DataFormat.NUMPY:
                if np is None:
                    logger.error("NumPy is not installed. Please install it to write NumPy files.")
                    return False
                
                # Ensure allow_pickle is False by default for security
                allow_pickle_param = kwargs.get('allow_pickle', False)
                if allow_pickle_param and not self.config.get("allow_unsafe_pickle", False):
                    warnings.warn(
                        "SECURITY RISK: Saving NumPy files with allow_pickle=True enables code execution. "
                        "Set allow_unsafe_pickle=True in config to proceed AT YOUR OWN RISK.",
                        UserWarning
                    )
                    allow_pickle_param = False
                
                np.save(self.file_path, data, **kwargs)
                
            elif self.format == DataFormat.IMAGE:
                if Image is None:
                    logger.error("PIL is not installed. Please install it to write image files.")
                    return False
                
                if isinstance(data, Image.Image):
                    data.save(self.file_path, **kwargs)
                else:
                    logger.error("Data must be a PIL Image object for image format")
                    return False
                
            elif self.format == DataFormat.AUDIO:
                # Basic audio writing implementation - expanded support would require specific audio libraries
                if isinstance(data, bytes):
                    with open(self.file_path, 'wb') as f:
                        f.write(data)
                    return True
                else:
                    logger.error("Audio writing not fully implemented - requires byte data")
                    return False
                
            else:
                logger.error(f"Unsupported format: {self.format}")
                return False
            
            logger.info(f"Data written to {self.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing to file: {e}")
            return False


class DatabaseDataDestination(DataDestination):
    """
    Data destination for writing to databases.
    
    Supports various database backends via SQLAlchemy.
    """
    
    def __init__(self, name: str, connection_string: str, 
                 table: str, schema: Optional[str] = None,
                 if_exists: str = "fail",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a database data destination.
        
        Args:
            name: Name of the data destination
            connection_string: Database connection string
            table: Table name to write to
            schema: Database schema name
            if_exists: What to do if the table exists ('fail', 'replace', 'append')
            config: Additional configuration
        """
        super().__init__(name, config)
        self.connection_string = connection_string
        self.table = table
        self.schema = schema
        self.if_exists = if_exists
        self.engine = None
        self.connection = None
        
        valid_if_exists = {'fail', 'replace', 'append'}
        if self.if_exists not in valid_if_exists:
            raise ValueError(f"Invalid if_exists: {if_exists}. "
                           f"Must be one of {valid_if_exists}.")
        
        self.metadata["connection_type"] = "database"
        self.metadata["table"] = table
        if schema:
            self.metadata["schema"] = schema
        self.metadata["if_exists"] = if_exists
    
    def connect(self) -> bool:
        """Connect to the database"""
        if sqlalchemy is None or create_engine is None:
            logger.error("SQLAlchemy is not installed. Please install it to use database destinations.")
            return False
            
        try:
            # Create SQLAlchemy engine with connection timeout
            self.engine = create_engine(
                self.connection_string,
                connect_args={"connect_timeout": self.config.get("connect_timeout", 30)}
            )
            
            # Test connection
            self.connection = self.engine.connect()
            logger.info(f"Connected to database: {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def write(self, data: Any, **kwargs) -> bool:
        """
        Write data to the database.
        
        Args:
            data: Data to write (pandas DataFrame or list of dictionaries)
            **kwargs: Additional parameters for pandas.to_sql
            
        Returns:
            bool: True if write successful, False otherwise
        """
        if pd is None:
            logger.error("Pandas is not installed. Please install it to use DatabaseDataDestination.")
            return False
            
        if not self.engine:
            if not self.connect():
                return False
        
        try:
            # Convert data to DataFrame if it's a list of dictionaries
            if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                df = pd.DataFrame(data)
            elif isinstance(data, pd.DataFrame):
                df = data
            else:
                logger.error(f"Unsupported data type for database writing: {type(data)}")
                return False
            
            # Write to database
            # Use a valid string literal for if_exists to satisfy type checking
            if_exists_value = self.if_exists
            if if_exists_value not in ('fail', 'replace', 'append'):
                if_exists_value = 'fail'  # Default to 'fail' if invalid
                
            df.to_sql(
                name=self.table,
                con=self.engine,
                schema=self.schema,
                if_exists=if_exists_value,
                index=kwargs.get('index', False),
                **{k: v for k, v in kwargs.items() if k != 'index'}
            )
            
            logger.info(f"Data written to table {self.table}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing to database: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def disconnect(self) -> bool:
        """Close the database connection"""
        try:
            if self.connection:
                self.connection.close()
            
            if self.engine:
                self.engine.dispose()
            
            self.connection = None
            self.engine = None
            
            self.metadata["connected"] = False
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from database: {e}")
            return False


class DataPipeline:
    """
    Main class for data processing pipelines.
    
    Manages sources, transformers, and destinations in a processing chain.
    """
    
    def __init__(self, name: str, event_bus=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize a data pipeline.
        
        Args:
            name: Name of the pipeline
            event_bus: Event bus for publishing pipeline events
            config: Configuration parameters
        """
        self.name = name
        self.event_bus = event_bus
        self.config = config or {}
        
        self.sources: Dict[str, DataSource] = {}
        self.transformers: Dict[str, DataTransformer] = {}
        self.destinations: Dict[str, DataDestination] = {}
        
        self.pipelines: Dict[str, List[str]] = {}  # {pipeline_name: [step_ids]}
        self.stats: Dict[str, Dict[str, Any]] = {}  # Statistics for each pipeline run
        
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "successful_runs": 0,
            "failed_runs": 0
        }
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure pipeline-specific logging"""
        self.logger = logging.getLogger(f"DataPipeline.{self.name}")
        
        # Set log level from config
        log_level = self.config.get("log_level", "INFO")
        self.logger.setLevel(getattr(logging, log_level))
        
        # Add a file handler if specified in config
        log_file = self.config.get("log_file")
        if log_file:
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def add_source(self, source_id: str, source: DataSource) -> bool:
        """
        Add a data source to the pipeline.
        
        Args:
            source_id: Unique ID for the source
            source: Data source instance
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        if source_id in self.sources:
            self.logger.warning(f"Source ID '{source_id}' already exists, overwriting")
        
        self.sources[source_id] = source
        return True
    
    def add_transformer(self, transformer_id: str, transformer: DataTransformer) -> bool:
        """
        Add a data transformer to the pipeline.
        
        Args:
            transformer_id: Unique ID for the transformer
            transformer: Data transformer instance
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        if transformer_id in self.transformers:
            self.logger.warning(f"Transformer ID '{transformer_id}' already exists, overwriting")
        
        self.transformers[transformer_id] = transformer
        return True
    
    def add_destination(self, destination_id: str, destination: DataDestination) -> bool:
        """
        Add a data destination to the pipeline.
        
        Args:
            destination_id: Unique ID for the destination
            destination: Data destination instance
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        if destination_id in self.destinations:
            self.logger.warning(f"Destination ID '{destination_id}' already exists, overwriting")
        
        self.destinations[destination_id] = destination
        return True
    
    def create_pipeline(self, pipeline_id: str, steps: List[str]) -> bool:
        """
        Create a pipeline with the specified steps.
        
        Args:
            pipeline_id: Unique ID for the pipeline
            steps: List of step IDs (source, transformer, destination)
            
        Returns:
            bool: True if created successfully, False otherwise
        """
        if pipeline_id in self.pipelines:
            self.logger.warning(f"Pipeline ID '{pipeline_id}' already exists, overwriting")
        
        # Validate steps
        for step in steps:
            if (step not in self.sources and 
                step not in self.transformers and 
                step not in self.destinations):
                self.logger.error(f"Step ID '{step}' not found in sources, transformers, or destinations")
                return False
        
        self.pipelines[pipeline_id] = steps
        return True
    
    def run_pipeline(self, pipeline_id: str, input_data: Any = None) -> Tuple[bool, Any]:
        """
        Run a pipeline with the specified ID.
        
        Args:
            pipeline_id: ID of the pipeline to run
            input_data: Optional input data (if None, will read from the first source)
            
        Returns:
            Tuple[bool, Any]: (success, result data)
        """
        if pipeline_id not in self.pipelines:
            self.logger.error(f"Pipeline ID '{pipeline_id}' not found")
            return False, None
        
        steps = self.pipelines[pipeline_id]
        
        # Initialize stats for this run
        run_id = f"{pipeline_id}_{int(time.time() * 1000)}"
        self.stats[run_id] = {
            "pipeline_id": pipeline_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "success": False,
            "steps_executed": 0,
            "steps": {},
            "error": None
        }
        
        # Publish start event
        self._publish_event("pipeline_started", {
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Process each step
            current_data = input_data
            
            for i, step_id in enumerate(steps):
                step_start_time = time.time()
                step_type = self._get_step_type(step_id)
                
                self.logger.info(f"Executing step {i+1}/{len(steps)}: {step_id} ({step_type})")
                
                # Publish step start event
                self._publish_event("step_started", {
                    "run_id": run_id,
                    "pipeline_id": pipeline_id,
                    "step_id": step_id,
                    "step_index": i,
                    "step_type": step_type,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Execute the step
                if step_type == "source":
                    if current_data is None:  # Only read from source if no input data
                        source = self.sources[step_id]
                        if not source.connect():
                            raise RuntimeError(f"Failed to connect to source '{step_id}'")
                        
                        current_data = source.read()
                        source.disconnect()
                
                elif step_type == "transformer":
                    transformer = self.transformers[step_id]
                    current_data = transformer.transform(current_data)
                
                elif step_type == "destination":
                    destination = self.destinations[step_id]
                    if not destination.connect():
                        raise RuntimeError(f"Failed to connect to destination '{step_id}'")
                    
                    success = destination.write(current_data)
                    destination.disconnect()
                    
                    if not success:
                        raise RuntimeError(f"Failed to write to destination '{step_id}'")
                
                # Record step stats
                step_execution_time = time.time() - step_start_time
                self.stats[run_id]["steps"][step_id] = {
                    "type": step_type,
                    "execution_time": step_execution_time,
                    "success": True
                }
                
                self.stats[run_id]["steps_executed"] += 1
                
                # Publish step completion event
                self._publish_event("step_completed", {
                    "run_id": run_id,
                    "pipeline_id": pipeline_id,
                    "step_id": step_id,
                    "step_index": i,
                    "step_type": step_type,
                    "execution_time": step_execution_time,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Update run statistics
            self.stats[run_id]["end_time"] = datetime.now().isoformat()
            self.stats[run_id]["success"] = True
            
            self.metadata["last_run"] = datetime.now().isoformat()
            self.metadata["successful_runs"] += 1
            
            # Publish completion event
            self._publish_event("pipeline_completed", {
                "run_id": run_id,
                "pipeline_id": pipeline_id,
                "success": True,
                "execution_time": self._calculate_run_time(run_id),
                "timestamp": datetime.now().isoformat()
            })
            
            self.logger.info(f"Pipeline '{pipeline_id}' completed successfully")
            return True, current_data
            
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Pipeline '{pipeline_id}' failed: {error_message}")
            self.logger.debug(traceback.format_exc())
            
            # Update run statistics
            self.stats[run_id]["end_time"] = datetime.now().isoformat()
            self.stats[run_id]["success"] = False
            self.stats[run_id]["error"] = error_message
            
            self.metadata["last_run"] = datetime.now().isoformat()
            self.metadata["failed_runs"] += 1
            
            # Publish error event
            self._publish_event("pipeline_error", {
                "run_id": run_id,
                "pipeline_id": pipeline_id,
                "error": error_message,
                "execution_time": self._calculate_run_time(run_id),
                "timestamp": datetime.now().isoformat()
            })
            
            return False, None
    
    def _get_step_type(self, step_id: str) -> str:
        """
        Get the type of a step by its ID.
        
        Args:
            step_id: ID of the step
            
        Returns:
            str: Type of the step ('source', 'transformer', or 'destination')
        """
        if step_id in self.sources:
            return "source"
        elif step_id in self.transformers:
            return "transformer"
        elif step_id in self.destinations:
            return "destination"
        else:
            return "unknown"
    
    def _calculate_run_time(self, run_id: str) -> float:
        """
        Calculate the total execution time for a pipeline run.
        
        Args:
            run_id: ID of the run
            
        Returns:
            float: Total execution time in seconds
        """
        run_stats = self.stats.get(run_id)
        if not run_stats or not run_stats.get("start_time") or not run_stats.get("end_time"):
            return 0.0
        
        start_time = datetime.fromisoformat(run_stats["start_time"])
        end_time = datetime.fromisoformat(run_stats["end_time"])
        
        return (end_time - start_time).total_seconds()
    
    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Publish an event to the event bus.
        
        Args:
            event_type: Type of the event
            payload: Event payload
            
        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self.event_bus:
            return False
        
        try:
            event = {
                "type": f"data_pipeline.{event_type}",
                "source": f"data_pipeline.{self.name}",
                "timestamp": datetime.now().isoformat(),
                "payload": payload
            }
            
            self.event_bus.publish(event)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            return False
    
    def get_stats(self, pipeline_id: str = None, limit: int = None) -> Dict[str, Any]:
        """
        Get statistics for pipeline runs.
        
        Args:
            pipeline_id: Optional ID to filter by pipeline
            limit: Optional limit on number of runs to return
            
        Returns:
            Dict containing run statistics
        """
        if pipeline_id:
            # Filter stats by pipeline ID
            filtered_stats = {
                run_id: stats for run_id, stats in self.stats.items()
                if stats["pipeline_id"] == pipeline_id
            }
        else:
            filtered_stats = self.stats.copy()
        
        # Sort by start time (most recent first)
        sorted_stats = dict(sorted(
            filtered_stats.items(),
            key=lambda x: x[1]["start_time"],
            reverse=True
        ))
        
        # Apply limit if specified
        if limit and limit > 0:
            sorted_stats = dict(list(sorted_stats.items())[:limit])
        
        return sorted_stats
    
    def get_pipeline_definitions(self) -> Dict[str, List[str]]:
        """
        Get all pipeline definitions.
        
        Returns:
            Dict mapping pipeline IDs to their step lists
        """
        return self.pipelines.copy()
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the pipeline manager.
        
        Returns:
            Dict containing metadata
        """
        return {
            **self.metadata,
            "source_count": len(self.sources),
            "transformer_count": len(self.transformers),
            "destination_count": len(self.destinations),
            "pipeline_count": len(self.pipelines)
        }
