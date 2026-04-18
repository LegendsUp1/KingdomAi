#!/usr/bin/env python3
"""
Strategy Validator for Kingdom AI Strategy Marketplace

This module provides validation and testing functionality for trading strategies
in the Strategy Marketplace.
"""

import logging
import inspect
import importlib.util
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

logger = logging.getLogger("KingdomAI.StrategyValidator")

class StrategyValidator:
    """
    Validator for testing and verifying trading strategies.
    
    This component provides safety checks, backtesting, and validation
    for strategies in the Strategy Marketplace.
    """
    
    def __init__(self, config=None, trading_system=None, market_api=None):
        """
        Initialize the strategy validator.
        
        Args:
            config: Configuration settings for the validator
            trading_system: Reference to the Trading System component
            market_api: Reference to the Market API component
        """
        self.config = config or {}
        self.logger = logger
        
        # Component connections
        self.trading_system = trading_system
        self.market_api = market_api
        
        # Validation settings
        self.min_backtest_days = self.config.get("min_backtest_days", 30)
        self.banned_imports = self.config.get("banned_imports", [
            "subprocess", "os.system", "eval", "exec", "socket", "requests", 
            "pickle", "marshal", "shutil", "multiprocessing"
        ])
        self.allowed_apis = self.config.get("allowed_apis", [
            "pandas", "numpy", "ta", "talib", "sklearn", "pandas_ta", "yfinance"
        ])
        
    async def validate_strategy(self, strategy: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a trading strategy.
        
        Args:
            strategy: Strategy data including code
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation results)
        """
        try:
            if "code" not in strategy:
                return False, {"error": "Strategy has no code to validate"}
                
            validation_results = {
                "timestamp": datetime.now().isoformat(),
                "syntactic_validation": None,
                "security_validation": None,
                "functional_validation": None,
                "backtest_results": None,
                "overall_result": False,
                "warnings": [],
                "errors": []
            }
            
            # Step 1: Syntactic validation
            syntax_result, syntax_details = await self.validate_syntax(strategy["code"])
            validation_results["syntactic_validation"] = {
                "passed": syntax_result,
                "details": syntax_details
            }
            
            if not syntax_result:
                validation_results["errors"].append(f"Syntax validation failed: {syntax_details.get('error', 'Unknown error')}")
                validation_results["overall_result"] = False
                return False, validation_results
                
            # Step 2: Security validation
            security_result, security_details = await self.validate_security(strategy["code"])
            validation_results["security_validation"] = {
                "passed": security_result,
                "details": security_details
            }
            
            if not security_result:
                validation_results["errors"].append(f"Security validation failed: {security_details.get('error', 'Unknown error')}")
                validation_results["overall_result"] = False
                return False, validation_results
                
            # Step 3: Functional validation
            functional_result, functional_details = await self.validate_functionality(strategy)
            validation_results["functional_validation"] = {
                "passed": functional_result,
                "details": functional_details
            }
            
            if not functional_result:
                validation_results["errors"].append(f"Functional validation failed: {functional_details.get('error', 'Unknown error')}")
                validation_results["overall_result"] = False
                return False, validation_results
                
            # Step 4: Backtesting (if available)
            if self.trading_system and hasattr(self.trading_system, "backtest_strategy"):
                backtest_result, backtest_details = await self.backtest_strategy(strategy)
                validation_results["backtest_results"] = backtest_details
                
                if not backtest_result and self.config.get("require_backtest_pass", False):
                    validation_results["errors"].append(f"Backtest validation failed: {backtest_details.get('error', 'Failed backtest')}")
                    validation_results["overall_result"] = False
                    return False, validation_results
                elif not backtest_result:
                    validation_results["warnings"].append(f"Backtest had poor performance: {backtest_details.get('warning', 'Performance concerns')}")
            else:
                validation_results["warnings"].append("Backtesting not available - trading system not connected")
                validation_results["backtest_results"] = {
                    "performed": False,
                    "details": "Backtesting capability not available"
                }
                
            # All validations passed
            validation_results["overall_result"] = True
            return True, validation_results
            
        except Exception as e:
            self.logger.error(f"Error validating strategy: {e}")
            return False, {"error": f"Validation failed: {str(e)}"}
    
    async def validate_syntax(self, code: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the syntax of the strategy code.
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation details)
        """
        try:
            # Attempt to compile the code
            compile(code, "<string>", "exec")
            
            return True, {"message": "Syntax validation passed"}
        except SyntaxError as e:
            return False, {
                "error": f"Syntax error at line {e.lineno}, column {e.offset}: {e.msg}",
                "line": e.lineno,
                "column": e.offset,
                "text": e.text
            }
        except Exception as e:
            return False, {"error": f"Syntax validation failed: {str(e)}"}
    
    async def validate_security(self, code: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the security of the strategy code.
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation details)
        """
        try:
            # Check for banned imports
            issues = []
            
            for banned in self.banned_imports:
                if f"import {banned}" in code or f"from {banned}" in code:
                    issues.append(f"Banned import: {banned}")
                    
            # Check for direct usage of dangerous functions
            danger_patterns = [
                "os.system(", "subprocess.", "eval(", "exec(", 
                "__import__", "globals()", "locals()", "getattr(", 
                "open(", "__class__", "__bases__", "__subclasses__"
            ]
            
            for pattern in danger_patterns:
                if pattern in code:
                    issues.append(f"Potentially dangerous pattern: {pattern}")
            
            if issues:
                return False, {
                    "error": "Security validation failed",
                    "issues": issues
                }
                
            return True, {"message": "Security validation passed"}
        except Exception as e:
            return False, {"error": f"Security validation failed: {str(e)}"}
    
    async def validate_functionality(self, strategy: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the functional aspects of the strategy.
        
        Args:
            strategy: Strategy data including code
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, validation details)
        """
        try:
            code = strategy.get("code", "")
            if not code:
                return False, {"error": "No code provided"}
                
            # Create a temporary file to import as a module
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
                temp_filename = temp_file.name
                temp_file.write(code.encode('utf-8'))
            
            try:
                # Import the module
                spec = importlib.util.spec_from_file_location("temp_strategy", temp_filename)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Check for required attributes/methods
                issues = []
                
                # Find strategy class (assume the main class in the module)
                strategy_class = None
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and obj.__module__ == module.__name__:
                        # Check if this might be a strategy class
                        if hasattr(obj, "execute") or hasattr(obj, "run") or "Strategy" in name:
                            strategy_class = obj
                            break
                
                if not strategy_class:
                    return False, {"error": "No strategy class found in code"}
                
                # Check required methods
                required_methods = ["__init__"]
                execution_methods = ["execute", "run", "process", "trade"]
                
                # At least one execution method is required
                has_execution_method = False
                for method in execution_methods:
                    if hasattr(strategy_class, method):
                        has_execution_method = True
                        break
                
                if not has_execution_method:
                    issues.append(f"Strategy class needs at least one execution method: {', '.join(execution_methods)}")
                
                # Check other required methods
                for method in required_methods:
                    if not hasattr(strategy_class, method):
                        issues.append(f"Missing required method: {method}")
                
                # Try to instantiate the class
                try:
                    params = {}
                    # Extract parameters from strategy if available
                    if "parameters" in strategy:
                        params = strategy["parameters"]
                    
                    # Instantiate with parameters
                    instance = strategy_class(**params)
                except Exception as e:
                    issues.append(f"Failed to instantiate strategy class: {str(e)}")
                
                if issues:
                    return False, {
                        "error": "Functional validation failed",
                        "issues": issues
                    }
                
                return True, {"message": "Functional validation passed"}
                
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
                    
        except Exception as e:
            self.logger.error(f"Error validating functionality: {e}")
            return False, {"error": f"Functional validation failed: {str(e)}"}
    
    async def backtest_strategy(self, strategy: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Backtest a trading strategy.
        
        Args:
            strategy: Strategy data including code
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (success, backtest results)
        """
        try:
            # Check if trading system is available
            if not self.trading_system or not hasattr(self.trading_system, "backtest_strategy"):
                return False, {"error": "Backtesting capability not available"}
                
            # Get strategy code
            code = strategy.get("code", "")
            if not code:
                return False, {"error": "No code provided for backtesting"}
                
            # Get backtest parameters
            markets = strategy.get("markets", ["BTC/USD"])
            start_date = datetime.now() - timedelta(days=self.min_backtest_days)
            end_date = datetime.now()
            timeframe = strategy.get("timeframe", "1h")
            
            # Perform backtest
            backtest_results = await self.trading_system.backtest_strategy(
                code=code,
                markets=markets,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                parameters=strategy.get("parameters", {})
            )
            
            # Evaluate backtest results
            if backtest_results.get("error"):
                return False, {"error": backtest_results["error"]}
                
            # Extract performance metrics
            profit_factor = backtest_results.get("profit_factor", 0)
            win_rate = backtest_results.get("win_rate", 0)
            sharpe_ratio = backtest_results.get("sharpe_ratio", 0)
            max_drawdown = backtest_results.get("max_drawdown", 0)
            total_trades = backtest_results.get("total_trades", 0)
            
            # Evaluate backtest performance
            passed = True
            warnings = []
            
            # Minimum criteria for a successful backtest
            if profit_factor < 1.0:
                passed = False
                warnings.append("Profit factor below 1.0 (unprofitable strategy)")
                
            if win_rate < 0.4:
                passed = False
                warnings.append("Win rate below 40%")
                
            if sharpe_ratio < 0.5:
                passed = False
                warnings.append("Sharpe ratio below 0.5 (poor risk-adjusted returns)")
                
            if max_drawdown > 0.3:
                passed = False
                warnings.append("Maximum drawdown exceeds 30%")
                
            if total_trades < 20:
                warnings.append("Low sample size (less than 20 trades)")
                
            # Return results
            return passed, {
                "passed": passed,
                "warnings": warnings if warnings else None,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "markets": markets,
                "timeframe": timeframe,
                "total_trades": total_trades,
                "profit_factor": profit_factor,
                "win_rate": win_rate,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "detailed_results": backtest_results
            }
                
        except Exception as e:
            self.logger.error(f"Error during backtesting: {e}")
            return False, {"error": f"Backtesting failed: {str(e)}"}
