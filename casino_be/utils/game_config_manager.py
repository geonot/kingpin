"""
Secure Game Configuration Manager
Handles server-side game configuration storage and validation
"""

import json
import os
from typing import Dict, Any, Optional
from flask import current_app
from casino_be.models import db, Slot # Absolute import
import time # Moved time import to top

class GameConfigManager:
    """Secure manager for game configurations"""
    
    _config_cache = {}
    _cache_timestamp = {}
    CACHE_TTL = 300  # 5 minutes cache TTL
    
    @classmethod
    def get_game_config(cls, slot_id: int) -> Optional[Dict[str, Any]]:
        """
        Get game configuration for a slot (server-side only)
        Returns sanitized config without sensitive payout information
        """
        try:
            # Check cache first
            cache_key = f"slot_{slot_id}"
            current_time = time.time()
            
            if (cache_key in cls._config_cache and 
                cache_key in cls._cache_timestamp and
                current_time - cls._cache_timestamp[cache_key] < cls.CACHE_TTL):
                return cls._config_cache[cache_key]
            
            # Load from database
            slot = Slot.query.get(slot_id)
            if not slot:
                current_app.logger.error(f"Slot {slot_id} not found in database")
                return None
            
            # Build secure config from database
            config = cls._build_secure_config(slot)
            
            # Cache the result
            cls._config_cache[cache_key] = config
            cls._cache_timestamp[cache_key] = current_time
            
            return config
            
        except Exception as e:
            current_app.logger.error(f"Error loading game config for slot {slot_id}: {str(e)}")
            return None
    
    @classmethod
    def get_client_config(cls, slot_id: int) -> Optional[Dict[str, Any]]:
        """
        Get sanitized configuration for client-side use
        Removes all sensitive payout and game logic information
        """
        config = cls.get_game_config(slot_id)
        if not config:
            return None
        
        # Return only UI and visual elements for client
        client_config = {
            "game": {
                "name": config["game"]["name"],
                "short_name": config["game"]["short_name"],
                "asset_dir": config["game"]["asset_dir"],
                "layout": {
                    "rows": config["game"]["layout"]["rows"],
                    "columns": config["game"]["layout"]["columns"]
                },
                "ui": config["game"].get("ui", {}),
                "reel": config["game"].get("reel", {}),
                "background": config["game"].get("background", {}),
                "animations": config["game"].get("animations", {}),
                "sound": config["game"].get("sound", {}),
                "settings": {
                    "soundDefault": config["game"].get("settings", {}).get("soundDefault", True), # Ensuring safe get
                    "turboDefault": config["game"].get("settings", {}).get("turboDefault", False) # Ensuring safe get
                    # Remove betOptions - these come from SlotBet table
                }
            }
        }
        
        return client_config
    
    @classmethod
    def _build_secure_config(cls, slot: 'Slot') -> Dict[str, Any]:
        """Build secure configuration from database slot object"""
        
        # Build symbols from database relationships
        symbols = []
        for symbol_model in slot.symbols: # Renamed variable for clarity
            symbol_data = {
                "id": symbol_model.symbol_internal_id,
                "name": symbol_model.name,
                "img_link": symbol_model.img_link,
                # "value" or "value_multiplier" for config based on how game logic consumes it.
                # SlotSymbol model has value_multiplier (Float). Game logic might expect a dict.
                # For now, providing what's directly on the model.
                "value_multiplier": float(symbol_model.value_multiplier) if symbol_model.value_multiplier is not None else 0.0,
                "is_wild": slot.wild_symbol_id is not None and symbol_model.symbol_internal_id == slot.wild_symbol_id,
                "is_scatter": slot.scatter_symbol_id is not None and symbol_model.symbol_internal_id == slot.scatter_symbol_id
            }
            # If symbol_model.data contains 'value_multipliers' or 'scatter_payouts', add them.
            if symbol_model.data:
                if 'value_multipliers' in symbol_model.data:
                    symbol_data['value_multipliers'] = symbol_model.data['value_multipliers']
                if 'scatter_payouts' in symbol_model.data:
                    symbol_data['scatter_payouts'] = symbol_model.data['scatter_payouts']
            
            symbols.append(symbol_data)
        
        # Build paylines from slot configuration
        paylines = []
        if hasattr(slot, 'paylines') and slot.paylines: # Guard access
            for i, payline in enumerate(slot.paylines):
                paylines.append({
                    "id": f"payline_{i+1}",
                    "coords": payline
                })
        
        # Build base configuration
        config = {
            "game": {
                "slot_id": slot.id,
                "name": slot.name,
                "short_name": slot.short_name,
                "asset_dir": f"/slots/{slot.short_name}/",
                "layout": {
                    "rows": slot.num_rows, # Corrected attribute
                    "columns": slot.num_columns, # Corrected attribute
                    "paylines": paylines
                },
                "symbols": symbols,
                "wild_symbol_id": slot.wild_symbol_id, # Directly from slot model
                "scatter_symbol_id": slot.scatter_symbol_id, # Directly from slot model
                "is_multiway": slot.is_multiway,
                "reel_configurations": slot.reel_configurations if slot.is_multiway else None
            }
        }
        
        # Add bonus features if configured
        # Construct bonus_features from individual fields if they exist and are relevant
        bonus_features_data = {}
        if hasattr(slot, 'bonus_type') and slot.bonus_type and slot.bonus_type == "free_spins": # Example check
            bonus_features_data["free_spins"] = {}
            if hasattr(slot, 'bonus_spins_trigger_count'):
                bonus_features_data["free_spins"]["trigger_count"] = slot.bonus_spins_trigger_count
            if hasattr(slot, 'bonus_spins_awarded'):
                bonus_features_data["free_spins"]["spins_awarded"] = slot.bonus_spins_awarded
            if hasattr(slot, 'bonus_multiplier'):
                bonus_features_data["free_spins"]["multiplier"] = slot.bonus_multiplier
            # Add other bonus types or sub-configurations as needed based on model fields

        if bonus_features_data.get("free_spins"): # Only add if "free_spins" key was populated
            config["game"]["bonus_features"] = bonus_features_data
        
        return config
    
    @classmethod
    def validate_game_config(cls, config: Dict[str, Any]) -> bool:
        """Validate game configuration for security and consistency"""
        try:
            game = config.get("game", {})
            
            # Required fields validation
            required_fields = ["slot_id", "name", "layout", "symbols"]
            for field in required_fields:
                if field not in game:
                    current_app.logger.error(f"Missing required field in game config: {field}")
                    return False
            
            # Layout validation
            layout = game["layout"]
            if not isinstance(layout.get("rows"), int) or layout["rows"] < 1:
                return False
            if not isinstance(layout.get("columns"), int) or layout["columns"] < 1:
                return False
            
            # Symbols validation
            symbols = game["symbols"]
            if not isinstance(symbols, list) or len(symbols) == 0:
                return False
            
            # Validate each symbol
            for symbol in symbols:
                if not isinstance(symbol.get("id"), int):
                    return False
                if not isinstance(symbol.get("weight"), (int, float)) or symbol["weight"] < 0:
                    return False
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error validating game config: {str(e)}")
            return False
    
    @classmethod
    def clear_cache(cls, slot_id: Optional[int] = None):
        """Clear configuration cache"""
        if slot_id:
            cache_key = f"slot_{slot_id}"
            cls._config_cache.pop(cache_key, None)
            cls._cache_timestamp.pop(cache_key, None)
        else:
            cls._config_cache.clear()
            cls._cache_timestamp.clear()

# Import time module # This redundant import will be removed
# import time