#!/usr/bin/env python3
"""
Quick test to verify winning lines structure from spin handler
"""
import os
import sys

# Add the casino_be directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'casino_be'))

from utils.spin_handler import calculate_win

def test_winning_lines():
    """Test calculate_win to see what winning_lines structure looks like"""
    
    # Test grid with a simple winning line
    grid = [
        [1, 1, 1, 2, 3],  # Row 0: Three 1s in a row
        [4, 5, 6, 7, 8],  # Row 1
        [9, 10, 11, 12, 13]  # Row 2
    ]
    
    # Simple payline configuration (top row)
    config_paylines = [
        {
            "id": "payline_1",
            "coords": [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4]]  # Top row
        }
    ]
    
    # Symbol configuration
    config_symbols_map = {
        1: {
            "id": 1,
            "name": "Symbol1", 
            "value_multipliers": {"3": 10.0, "4": 20.0, "5": 50.0}
        },
        2: {"id": 2, "name": "Symbol2"},
        3: {"id": 3, "name": "Symbol3"},
        4: {"id": 4, "name": "Symbol4"},
        5: {"id": 5, "name": "Symbol5"},
        6: {"id": 6, "name": "Symbol6"},
        7: {"id": 7, "name": "Symbol7"},
        8: {"id": 8, "name": "Symbol8"},
        9: {"id": 9, "name": "Symbol9"},
        10: {"id": 10, "name": "Symbol10"},
        11: {"id": 11, "name": "Symbol11"},
        12: {"id": 12, "name": "Symbol12"},
        13: {"id": 13, "name": "Symbol13"},
    }
    
    total_bet_sats = 100
    wild_symbol_id = None
    scatter_symbol_id = None
    min_symbols_to_match = None
    
    print("Testing calculate_win function...")
    print(f"Grid: {grid}")
    print(f"Paylines: {config_paylines}")
    print(f"Total bet: {total_bet_sats} sats")
    print()
    
    try:
        result = calculate_win(
            grid=grid,
            config_paylines=config_paylines,
            config_symbols_map=config_symbols_map,
            total_bet_sats=total_bet_sats,
            wild_symbol_id=wild_symbol_id,
            scatter_symbol_id=scatter_symbol_id,
            min_symbols_to_match=min_symbols_to_match
        )
        
        print("=== RESULTS ===")
        print(f"Total win (sats): {result['total_win_sats']}")
        print(f"Number of winning lines: {len(result['winning_lines'])}")
        print()
        
        print("=== WINNING LINES STRUCTURE ===")
        for i, line in enumerate(result['winning_lines']):
            print(f"Line {i+1}:")
            for key, value in line.items():
                print(f"  {key}: {value}")
            print()
            
        print("=== WINNING SYMBOL COORDS ===")
        print(f"Winning coords: {result['winning_symbol_coords']}")
        
        return result
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_winning_lines()
