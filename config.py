"""
Configuration loader utility
Provides a unified way to load and manage configuration
"""

import yaml
import os
import logging
from typing import Dict, Any

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file
    
    Args:
        config_path (str): Path to configuration file
        
    Returns:
        Dict[str, Any]: Configuration dictionary
    """
    try:
        # Handle both absolute and relative paths
        if not os.path.isabs(config_path):
            # If relative path, make it relative to script location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, config_path)
        
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        if not config:
            raise ValueError("Configuration file is empty or invalid")
            
        return config
        
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML configuration: {e}")
        raise ValueError(f"Invalid YAML configuration: {e}")
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        raise Exception(f"Failed to load configuration: {e}")

def save_config(config: Dict[str, Any], config_path: str = "config.yaml") -> bool:
    """
    Save configuration to YAML file
    
    Args:
        config (Dict[str, Any]): Configuration dictionary to save
        config_path (str): Path to configuration file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Handle both absolute and relative paths
        if not os.path.isabs(config_path):
            # If relative path, make it relative to script location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, config_path)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, indent=2, allow_unicode=True)
            
        logging.info(f"Configuration saved successfully to: {config_path}")
        return True
        
    except Exception as e:
        logging.error(f"Error saving configuration: {e}")
        return False

def get_fyers_config(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract Fyers-specific configuration
    
    Args:
        config (Dict[str, Any]): Full configuration dictionary
        
    Returns:
        Dict[str, str]: Fyers configuration
    """
    fyers_config = config.get('api', {})
    
    # Map to match your existing structure if needed
    if 'fyers' in config:
        # Support both 'api' and 'fyers' keys for backward compatibility
        fyers_legacy = config.get('fyers', {})
        fyers_config.update(fyers_legacy)
    
    return fyers_config

def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration has required fields
    
    Args:
        config (Dict[str, Any]): Configuration dictionary
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = {
        'api': ['client_id', 'secret_key', 'redirect_uri'],
        'trading': ['symbols'],
        'trading.risk_management': ['stop_loss_points', 'target_points'],
        'timing': ['market_open_time', 'first_candle_end_time']
    }
    
    try:
        for section, fields in required_fields.items():
            if '.' in section:
                # Handle nested sections
                sections = section.split('.')
                current = config
                for s in sections:
                    if s not in current:
                        logging.error(f"Missing configuration section: {section}")
                        return False
                    current = current[s]
                section_config = current
            else:
                if section not in config:
                    logging.error(f"Missing configuration section: {section}")
                    return False
                section_config = config[section]
            
            for field in fields:
                if field not in section_config:
                    logging.error(f"Missing required field: {section}.{field}")
                    return False
                    
                # Check for placeholder values
                value = section_config[field]
                if isinstance(value, str) and value.startswith("YOUR_"):
                    logging.warning(f"Placeholder value found for {section}.{field}")
                    return False
        
        logging.info("Configuration validation passed")
        return True
        
    except Exception as e:
        logging.error(f"Error validating configuration: {e}")
        return False

def update_config_field(config_path: str, section: str, field: str, value: Any) -> bool:
    """
    Update a specific field in the configuration
    
    Args:
        config_path (str): Path to configuration file
        section (str): Configuration section
        field (str): Field name
        value (Any): New value
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config = load_config(config_path)
        
        if section not in config:
            config[section] = {}
            
        config[section][field] = value
        
        return save_config(config, config_path)
        
    except Exception as e:
        logging.error(f"Error updating configuration field: {e}")
        return False

if __name__ == "__main__":
    # Test the configuration loader
    try:
        config = load_config()
        print("✅ Configuration loaded successfully")
        
        if validate_config(config):
            print("✅ Configuration validation passed")
        else:
            print("❌ Configuration validation failed")
            
        fyers_config = get_fyers_config(config)
        print(f"🔑 Fyers Client ID: {fyers_config.get('client_id', 'Not configured')}")
        
    except Exception as e:
        print(f"❌ Error testing configuration: {e}")