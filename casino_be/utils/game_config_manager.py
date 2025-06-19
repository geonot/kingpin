"""
Secure Game Configuration Manager
Handles server-side game configuration storage and validation
"""

import json
import os
from typing import Dict, Any, Optional
from flask import current_app
from ..models import db, Slot # Relative import
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
                    "soundDefault": config["game"]["settings"].get("soundDefault", True),
                    "turboDefault": config["game"]["settings"].get("turboDefault", False)
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
        for symbol in slot.symbols:
            symbol_data = {
                "id": symbol.id,
                "name": symbol.name,
                "value": float(symbol.value) if symbol.value else None,
                "weight": symbol.weight,
                "is_wild": symbol.is_wild,
                "is_scatter": symbol.is_scatter,
                "icon": symbol.icon_path
            }
            
            # Add multipliers if they exist
            if symbol.value_multipliers:
                symbol_data["value_multipliers"] = symbol.value_multipliers
            if symbol.scatter_payouts:
                symbol_data["scatter_payouts"] = symbol.scatter_payouts
                
            symbols.append(symbol_data)
        
        # Build paylines from slot configuration
        paylines = []
        if slot.paylines:
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
                    "rows": slot.rows,
                    "columns": slot.columns,
                    "paylines": paylines
                },
                "symbols": symbols,
                "wild_symbol_id": next((s.id for s in slot.symbols if s.is_wild), None),
                "scatter_symbol_id": next((s.id for s in slot.symbols if s.is_scatter), None),
                "is_multiway": slot.is_multiway,
                "reel_configurations": slot.reel_configurations if slot.is_multiway else None
            }
        }
        
        # Add bonus features if configured
        if slot.bonus_features:
            config["game"]["bonus_features"] = slot.bonus_features
        
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