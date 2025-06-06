# casino_be/utils/slot_builder.py
"""
SlotBuilder: A utility script to automate the creation of themed slot games.

This script generates placeholder image assets, a gameConfig.json file,
and a database migration file for a new slot game based on a provided theme.

Usage:
  python slot_builder.py "Theme Name" [--slot_id N]

Arguments:
  theme: The theme idea for the slot game (e.g., 'Mystic Forest').
  slot_id (optional): Specific integer ID for the new slot game for DB entry.
                      If not provided, the script attempts to determine the next available ID.
"""

import argparse
import os
import re
import json
from datetime import datetime, timezone

# Attempt to import pgsql specific types, fallback if not available for some reason
try:
    from sqlalchemy.dialects import postgresql
    JSONB_TYPE = postgresql.JSONB
except ImportError:
    print("Warning: sqlalchemy.dialects.postgresql.JSONB not found. Falling back to sa.JSON.")
    from sqlalchemy import JSON as JSONB_TYPE # Fallback


def get_next_slot_id():
    """Determines the next available slot ID by scanning existing slot directories."""
    # Path relative to this script's location (casino_be/utils/)
    public_fe_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'casino_fe', 'public'))

    current_max_id = 0
    try:
        if not os.path.exists(public_fe_path):
            print(f"Warning: Frontend public path {public_fe_path} not found. Defaulting slot_id to 1.")
            return 1

        for item in os.listdir(public_fe_path):
            if os.path.isdir(os.path.join(public_fe_path, item)):
                # Match directories named 'slot<number>' (e.g., slot1, slot23)
                match = re.match(r'slot(\d+)', item) # Corrected regex
                if match:
                    slot_num = int(match.group(1))
                    if slot_num > current_max_id:
                        current_max_id = slot_num
    except OSError as e:
        print(f"Error scanning for existing slot IDs in {public_fe_path}: {e}. Defaulting to potentially unsafe next ID.")
        # Fallback or re-raise depending on desired strictness. For now, continue with current_max_id or 0.

    return current_max_id + 1

def generate_images(theme_name, short_name, slot_id, asset_path_for_creation):
    """
    Generates placeholder image files for the slot game theme.
    This includes background, bonus background, border, UI buttons, and symbols.
    Returns a list of dictionaries detailing the generated symbols for use in gameConfig.
    """
    print(f"INFO: Generating placeholder images for theme '{theme_name}' in {asset_path_for_creation}...")

    # Define all images to be generated, including types and prompt ideas
    image_specs = [
        {"filename": "bg.png", "prompt_idea": f"Expansive and thematic main background for a '{theme_name}' slot game.", "type": "background"},
        {"filename": "bbg.png", "prompt_idea": f"Special bonus round background for a '{theme_name}' slot game.", "type": "bonus_background"},
        {"filename": "border.png", "prompt_idea": f"Ornate slot machine border fitting a '{theme_name}' style.", "type": "border"},
        {"filename": "spin.png", "prompt_idea": f"Themed 'Spin' button for a '{theme_name}' slot game.", "type": "ui_button"},
        {"filename": "autospin.png", "prompt_idea": f"Themed 'Autospin' button for '{theme_name}'.", "type": "ui_button"},
        {"filename": "turbo.png", "prompt_idea": f"Themed 'Turbo Mode' button for '{theme_name}'.", "type": "ui_button"},
        # Symbols (11 total: 3 low, 3 mid, 2 high, scatter, bonus, wild)
        {"filename": "sprite_0.png", "prompt_idea": f"Low-value symbol 1 for '{theme_name}'. E.g., thematic fruit/relic.", "type": "low", "symbol_name": "Low Symbol 1"},
        {"filename": "sprite_1.png", "prompt_idea": f"Low-value symbol 2 for '{theme_name}'. E.g., thematic fruit/relic.", "type": "low", "symbol_name": "Low Symbol 2"},
        {"filename": "sprite_2.png", "prompt_idea": f"Low-value symbol 3 for '{theme_name}'. E.g., thematic fruit/relic.", "type": "low", "symbol_name": "Low Symbol 3"},
        {"filename": "sprite_3.png", "prompt_idea": f"Medium-value symbol 1 for '{theme_name}'. More detailed.", "type": "mid", "symbol_name": "Mid Symbol 1"},
        {"filename": "sprite_4.png", "prompt_idea": f"Medium-value symbol 2 for '{theme_name}'. More detailed.", "type": "mid", "symbol_name": "Mid Symbol 2"},
        {"filename": "sprite_5.png", "prompt_idea": f"Medium-value symbol 3 for '{theme_name}'. More detailed.", "type": "mid", "symbol_name": "Mid Symbol 3"},
        {"filename": "sprite_6.png", "prompt_idea": f"High-value symbol 1 for '{theme_name}'. Significant thematic element.", "type": "high", "symbol_name": "High Symbol 1"},
        {"filename": "sprite_7.png", "prompt_idea": f"High-value symbol 2 for '{theme_name}'. E.g., character/major object.", "type": "high", "symbol_name": "High Symbol 2"},
        {"filename": "sprite_8.png", "prompt_idea": f"'Scatter' symbol for '{theme_name}'. Visually distinct for features.", "type": "scatter", "symbol_name": "Scatter"},
        {"filename": "sprite_9.png", "prompt_idea": f"'Bonus' symbol for '{theme_name}'. Visually distinct for bonus rounds.", "type": "bonus", "symbol_name": "Bonus"},
        {"filename": "sprite_10.png", "prompt_idea": f"'Wild' symbol for '{theme_name}'. Substitutes symbols.", "type": "wild", "symbol_name": "Wild"},
    ]

    generated_symbol_details = []
    symbol_id_counter = 1 # Internal IDs for symbols, 1-based

    for spec in image_specs:
        image_file_path = os.path.join(asset_path_for_creation, spec['filename'])
        try:
            with open(image_file_path, 'w') as f:
                f.write(f"Placeholder for: {spec['filename']}\nTheme: {theme_name}\nIntended Gemini Prompt Idea: {spec['prompt_idea']}")
            # print(f"  DEBUG: Generated (placeholder) image: {spec['filename']}")
        except IOError as e:
            print(f"ERROR: Could not write image placeholder {image_file_path}: {e}")
            # Decide if to continue or raise error - for now, print and continue

        # If it's a symbol, add its details to the list
        if spec['type'] not in ['background', 'bonus_background', 'border', 'ui_button']:
            generated_symbol_details.append({
                "name": spec['symbol_name'],
                "file": spec['filename'],
                "type": spec['type'],
                "id": symbol_id_counter # This is the symbol_internal_id for DB and config
            })
            symbol_id_counter +=1

    print(f"INFO: Image placeholder generation phase complete. {len(image_specs)} placeholder images targeted.")
    return sorted(generated_symbol_details, key=lambda x: x['id'])

def generate_game_config(theme_name, short_name, slot_id, asset_dir_for_config, asset_path_for_creation, symbol_config_details,
                         is_cascading_arg=False, cascade_type_arg=None, min_symbols_to_match_arg=None, win_multipliers_arg_str="[]"):
    """
    Generates the gameConfig.json file for the new slot game.
    Populates based on theme, symbol details, and provided game mechanics.
    Saves the file to the specified asset creation path.
    Returns a dictionary of details for database migration.
    """
    print(f"INFO: Generating gameConfig.json for theme '{theme_name}' in {asset_path_for_creation}")

    # Symbol values for gameConfig.json (can differ from DB value_multiplier if needed)
    # IDs: 1-3 Low, 4-6 Mid, 7-8 High, 9 Scatter, 10 Bonus, 11 Wild
    symbol_values_config = {
        1: 1.0, 2: 1.5, 3: 2.0, # Low-value symbols
        4: 3.0, 5: 4.0, 6: 5.0, # Medium-value symbols
        7: 10.0, 8: 20.0,      # High-value symbols
        9: None, # Scatter symbol (value often handled by specific payout rules)
        10: None, # Bonus symbol (triggers feature, no direct pay value here)
        11: None  # Wild symbol (substitutes, no direct pay value here)
    }

    config_symbols_list = []
    for s_detail in symbol_config_details:
        symbol_obj = {
            "id": s_detail['id'], # This is the symbol_internal_id
            "icon": asset_dir_for_config + s_detail['file'], # Path like /theme_name/sprite_0.png
            "value": symbol_values_config.get(s_detail['id']), # Base value, might be None for non-paying
            "name": s_detail['name'],
            "is_wild": s_detail['id'] == 11, # Assuming ID 11 is Wild
            "is_scatter": s_detail['id'] == 9, # Assuming ID 9 is Scatter
            "is_bonus": s_detail['id'] == 10, # Assuming ID 10 is Bonus
            # Default weights assigned based on typical symbol roles/values
            "weight": 1.0 # Default, will be overridden below
        }

        # Assign specific default weights based on symbol ID conventions
        symbol_id = s_detail['id']
        if 1 <= symbol_id <= 3: # Low-value
            symbol_obj['weight'] = 10.0
        elif 4 <= symbol_id <= 6: # Medium-value
            symbol_obj['weight'] = 5.0
        elif 7 <= symbol_id <= 8: # High-value
            symbol_obj['weight'] = 2.0
        elif symbol_id == 9: # Scatter
            symbol_obj['weight'] = 1.0
        elif symbol_id == 10: # Bonus
            symbol_obj['weight'] = 1.0
        elif symbol_id == 11: # Wild
            symbol_obj['weight'] = 1.5
        # Ensure all symbols have a weight, even if it's a generic default already set

        s_value_for_payout = symbol_values_config.get(s_detail['id'])

        # Add value_multipliers for payable symbols (IDs 1-8 by convention)
        if s_value_for_payout is not None and not symbol_obj['is_wild'] and not symbol_obj['is_scatter'] and not symbol_obj['is_bonus']:
            symbol_obj['value_multipliers'] = {
                "3": s_value_for_payout * 1,
                "4": s_value_for_payout * 3,
                "5": s_value_for_payout * 5
            }

        # Add scatter_payouts for scatter symbol (ID 9 by convention)
        if symbol_obj['is_scatter']:
            symbol_obj['scatter_payouts'] = {
                "3": 5,
                "4": 15,
                "5": 50
            }

        # Wild and Bonus symbols typically don't have value_multipliers or scatter_payouts
        # cluster_payouts are deferred for this subtask.

        config_symbols_list.append(symbol_obj)

    # Base structure for gameConfig.json (can be loaded from a template file too)
    game_config_dict = {
        "game": {
            "slot_id": slot_id, # This is actual_db_slot_id from main
            "name": theme_name,
            "short_name": short_name,
            "asset_dir": asset_dir_for_config,
            "layout": {"rows": 3, "columns": 5},
            "symbol_count": len(symbol_config_details), # Should be 11
            "symbol_scatter": 9, # By convention, ID 9 is Scatter
            "symbol_wild": 11,    # By convention, ID 11 is Wild
            "symbol_bonus": 10,   # By convention, ID 10 is Bonus
            "symbols": config_symbols_list,
            "paylines": [
                {"id": 0, "coords": [[0,0],[0,1],[0,2],[0,3],[0,4]]},
                {"id": 1, "coords": [[1,0],[1,1],[1,2],[1,3],[1,4]]},
                {"id": 2, "coords": [[2,0],[2,1],[2,2],[2,3],[2,4]]},
                {"id": 3, "coords": [[0,0],[1,1],[2,2],[1,3],[0,4]]},
                {"id": 4, "coords": [[2,0],[1,1],[0,2],[1,3],[2,4]]},
                # Can add more default paylines if desired
            ],
            # "payouts": payouts_list, # Removed top-level payouts array
            "ui": { # Simplified UI section, can be expanded from a template
                "buttons": {
                    "spin": { "icon": asset_dir_for_config + "spin.png"},
                    "autoSpin": { "icon": asset_dir_for_config + "autospin.png"},
                    "turbo": { "icon": asset_dir_for_config + "turbo.png"},
                    "settings": { "icon": "/assets/ui/settings.png" } # Generic settings icon
                }
            },
            "reel": {"symbolSize": { "width": 100, "height": 100 }, "position": { "x": 150, "y": 100 } },
            "background": {"image": asset_dir_for_config + "bg.png"},
            "bonus_background": {"image": asset_dir_for_config + "bbg.png"},
            "animations": { "spin": { "duration": 800 }, "winLine": { "duration": 500 } }, # Simplified
            "bonus": {"triggerSymbolId": 10, "triggerCount": 3, "spinsAwarded": 10, "multiplier": 2.0},
            "sound": { "spin": "/assets/sounds/spin.wav" }, # Simplified, use generic sounds
            "settings": {"betOptions": [10, 20, 50, 100, 200, 500]},
            "reel_strips": [
                [1,2,3,4,5,6,7,8,9,10,11, 1,2,3,1,4,5,1,2,3,4,5,6,7,8], # Reel 1 (25 symbols)
                [1,2,3,4,5,6,7,8,9,10,11, 1,2,3,6,7,8,1,2,3,4,5,6,7,8], # Reel 2 (25 symbols)
                [1,2,3,4,5,6,7,8,9,10,11, 1,2,4,5,9,10,1,2,3,4,5,6,7,8],# Reel 3 (25 symbols)
                [1,2,3,4,5,6,7,8,9,10,11, 1,3,6,7,11,1,2,3,4,5,6,7,8],  # Reel 4 (25 symbols)
                [1,2,3,4,5,6,7,8,9,10,11, 2,4,5,8,9,1,2,3,4,5,6,7,8]   # Reel 5 (25 symbols)
            ],
            # Cascading features
            "is_cascading": is_cascading_arg,
            "cascade_type": cascade_type_arg if is_cascading_arg else None,
            "min_symbols_to_match": min_symbols_to_match_arg if is_cascading_arg else None,
            "win_multipliers": json.loads(win_multipliers_arg_str) if is_cascading_arg else []
        }
    }

    config_file_path = os.path.join(asset_path_for_creation, 'gameConfig.json')
    try:
        with open(config_file_path, 'w') as f:
            json.dump(game_config_dict, f, indent=2)
        print(f"INFO: Successfully generated gameConfig.json at {config_file_path}")
    except IOError as e:
        print(f"ERROR: Could not write gameConfig.json to {config_file_path}: {e}")
        # Decide how to handle this - script might need to stop or return failure
        return None # Indicate failure

    # Return details needed for DB migration
    return {
        "slot_name_db": theme_name,
        "short_name_db": short_name,
        "description_db": f"A fun slot game with a {theme_name} theme, created by SlotBuilder.",
        "num_rows_db": game_config_dict['game']['layout']['rows'],
        "num_columns_db": game_config_dict['game']['layout']['columns'],
        "num_symbols_db": game_config_dict['game']['symbol_count'],
        "wild_symbol_id_db": game_config_dict['game']['symbol_wild'], # Internal ID (1-11)
        "scatter_symbol_id_db": game_config_dict['game']['symbol_scatter'], # Internal ID (1-11)
        "bonus_symbol_id_db": game_config_dict['game']['symbol_bonus'], # Internal ID (1-11), for reference
        "asset_directory_db": asset_dir_for_config,
        "rtp_db": 96.0, # Default RTP
        "volatility_db": "Medium", # Default Volatility
        "bonus_type_db": "free_spins", # Generic bonus type for DB categorization
        "bonus_subtype_db": theme_name, # Specific theme for subtype
        "bonus_spins_trigger_count_db": game_config_dict['game']['bonus']['triggerCount'],
        "bonus_spins_awarded_db": game_config_dict['game']['bonus']['spinsAwarded'],
        "is_active_db": True,
        # Cascading fields for DB
        "is_cascading_db": game_config_dict['game']['is_cascading'],
        "cascade_type_db": game_config_dict['game']['cascade_type'],
        "min_symbols_to_match_db": game_config_dict['game']['min_symbols_to_match'],
        "win_multipliers_db": game_config_dict['game']['win_multipliers']
    }

def generate_migration_file(theme_name, short_name, slot_id, asset_dir_for_config, db_slot_details, symbol_db_details):
    """
    Generates an Alembic database migration file for the new slot game.
    Includes upgrade and downgrade functions for adding/removing the slot and its symbols.
    """
    print(f"INFO: Generating migration file for theme '{theme_name}' (Slot DB ID: {slot_id})")

    if not db_slot_details:
        print("ERROR: db_slot_details is missing. Cannot generate migration.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    migrations_dir = os.path.abspath(os.path.join(script_dir, '..', 'migrations', 'versions'))

    try:
        if not os.path.exists(migrations_dir):
            os.makedirs(migrations_dir)
            print(f"INFO: Created migrations directory: {migrations_dir}")
    except OSError as e:
        print(f"ERROR: Could not create migrations directory {migrations_dir}: {e}")
        return # Cannot proceed without migrations directory

    # Determine down_revision
    down_revision = None
    try:
        # Filter for .py files, not starting with __, and having a revision ID pattern
        existing_migrations = sorted([
            f for f in os.listdir(migrations_dir)
            if f.endswith('.py') and
               not f.startswith('__') and
               re.match(r'^[0-9a-zA-Z]+_', f) # Match typical Alembic revision ID prefix
        ])
        if existing_migrations:
            # Extract revision ID from the last file name (e.g., 'XXXXXXXXXXXX_desc.py' -> 'XXXXXXXXXXXX')
            match = re.match(r'^([0-9a-zA-Z]+)_', existing_migrations[-1])
            if match:
                down_revision = match.group(1)
    except OSError as e:
        print(f"Warning: Could not list existing migrations to determine down_revision: {e}. Setting to None.")

    # Generate new revision ID (timestamp + first 4 chars of short_name for some uniqueness)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    # Using a more common Alembic style for auto-generated IDs (e.g., first 12 of a UUID hex or a timestamp)
    new_revision_id = f"{timestamp}{short_name[:4].lower()}"

    migration_filename = f"{new_revision_id}_add_{short_name}_slot.py"
    migration_filepath = os.path.join(migrations_dir, migration_filename)

    # Prepare data for slot table insertion
    slot_insert_data = {
        'id': slot_id,
        'name': db_slot_details['slot_name_db'],
        'description': db_slot_details['description_db'],
        'num_rows': db_slot_details['num_rows_db'],
        'num_columns': db_slot_details['num_columns_db'],
        'num_symbols': db_slot_details['num_symbols_db'],
        'wild_symbol_id': db_slot_details['wild_symbol_id_db'], # Internal symbol ID
        'scatter_symbol_id': db_slot_details['scatter_symbol_id_db'], # Internal symbol ID
        'bonus_type': db_slot_details['bonus_type_db'],
        'bonus_subtype': db_slot_details['bonus_subtype_db'],
        'bonus_multiplier': 1.0, # Default value from Slot model, assuming it exists
        'bonus_spins_trigger_count': db_slot_details['bonus_spins_trigger_count_db'],
        'bonus_spins_awarded': db_slot_details['bonus_spins_awarded_db'],
        'short_name': db_slot_details['short_name_db'],
        'asset_directory': db_slot_details['asset_directory_db'],
        'rtp': db_slot_details['rtp_db'],
        'volatility': db_slot_details['volatility_db'],
        'is_active': db_slot_details['is_active_db'],
        'is_multiway': False,
        'reel_configurations': None,
        'is_cascading': db_slot_details['is_cascading_db'],
        'cascade_type': db_slot_details['cascade_type_db'],
        'min_symbols_to_match': db_slot_details['min_symbols_to_match_db'],
        'win_multipliers': db_slot_details['win_multipliers_db'],
        'created_at': datetime.now(timezone.utc)
    }

    # Prepare data for slot_symbol table insertion
    symbol_value_multipliers_db = { # For DB value_multiplier column
        1: 1.0, 2: 1.5, 3: 2.0, 4: 3.0, 5: 4.0, 6: 5.0, 7: 10.0, 8: 20.0, # Paying symbols
        9: 0.0, 10: 0.0, 11: 0.0  # Scatter, Bonus, Wild (typically no direct payout value)
    }
    symbols_insert_data_list = []
    for s_detail in symbol_db_details:
        symbols_insert_data_list.append({
            'slot_id': slot_id,
            'symbol_internal_id': s_detail['id'],
            'name': s_detail['name'],
            'img_link': asset_dir_for_config + s_detail['file'],
            'value_multiplier': symbol_value_multipliers_db.get(s_detail['id'], 0.0),
            'data': {} # Default to empty JSON object for 'data' field in SlotSymbol
        })

    # Helper to create string representation of dict for embedding in template
    def dict_to_py_string(d):
        parts = []
        for k, v in d.items():
            if isinstance(v, datetime):
                parts.append(f"'{k}': datetime.datetime.fromisoformat({repr(v.isoformat())})")
            else:
                parts.append(f"'{k}': {repr(v)}")
        return "{" + ", ".join(parts) + "}"

    slot_data_final_repr = dict_to_py_string(slot_insert_data)
    symbols_data_final_repr = "[" + ",\n        ".join([dict_to_py_string(s) for s in symbols_insert_data_list]) + "]"


    migration_template = f"""# Autogenerated migration for new slot: {theme_name}
\"\"\"
Revision ID: {new_revision_id}
Revises: {repr(down_revision)}
Create Date: {datetime.now(timezone.utc).isoformat()}
\"\"\"
from alembic import op
import sqlalchemy as sa
import datetime # Required for datetime.fromisoformat in generated code

# Attempt to import PostgreSQL specific types, fallback to generic JSON
try:
    from sqlalchemy.dialects import postgresql
    JSONB_TYPE = postgresql.JSONB(astext_type=sa.Text()) # Ensure astext_type for compatibility
except ImportError:
    JSONB_TYPE = sa.JSON

# revision identifiers, used by Alembic.
revision = '{new_revision_id}'
down_revision = {repr(down_revision)} # Uses repr to correctly format None or string
branch_labels = None
depends_on = None

def upgrade():
    # Define table structures for insertion (should mirror models.py)
    slot_table = sa.table('slot',
        sa.Column('id', sa.Integer()),
        sa.Column('name', sa.String(100)),
        sa.Column('description', sa.Text()),
        sa.Column('num_rows', sa.Integer()),
        sa.Column('num_columns', sa.Integer()),
        sa.Column('num_symbols', sa.Integer()),
        sa.Column('wild_symbol_id', sa.Integer()), # Internal symbol ID
        sa.Column('scatter_symbol_id', sa.Integer()), # Internal symbol ID
        sa.Column('bonus_type', sa.String(50)),
        sa.Column('bonus_subtype', sa.String(50)),
        sa.Column('bonus_multiplier', sa.Float()),
        sa.Column('bonus_spins_trigger_count', sa.Integer()),
        sa.Column('bonus_spins_awarded', sa.Integer()),
        sa.Column('short_name', sa.String(50)),
        sa.Column('asset_directory', sa.String(255)),
        sa.Column('rtp', sa.Float()),
        sa.Column('volatility', sa.String(20)),
        sa.Column('is_active', sa.Boolean()),
        sa.Column('is_multiway', sa.Boolean()),
        sa.Column('reel_configurations', JSONB_TYPE),
        sa.Column('is_cascading', sa.Boolean()),
        sa.Column('cascade_type', sa.String(50)),
        sa.Column('min_symbols_to_match', sa.Integer()),
        sa.Column('win_multipliers', JSONB_TYPE),
        sa.Column('created_at', sa.DateTime(timezone=True)) # Ensure timezone=True if model expects it
    )

    slot_symbol_table = sa.table('slot_symbol',
        sa.Column('id', sa.Integer()), # This is PK of slot_symbol, not used in bulk_insert if auto-gen
        sa.Column('slot_id', sa.Integer()),
        sa.Column('symbol_internal_id', sa.Integer()),
        sa.Column('name', sa.String(50)),
        sa.Column('img_link', sa.String(255)),
        sa.Column('value_multiplier', sa.Float()),
        sa.Column('data', JSONB_TYPE)
    )

    # Data for slot table (ensure it's a list of dicts)
    # The dict_to_py_string helper ensures datetime objects are correctly represented
    _slot_insert_data = [{slot_data_final_repr}]

    # Data for slot_symbol table
    _symbols_insert_data_list = {symbols_data_final_repr}

    op.bulk_insert(slot_table, _slot_insert_data)
    op.bulk_insert(slot_symbol_table, _symbols_insert_data_list)

    print(f"Migration {{revision}}: Inserted slot '{theme_name}' (DB ID: {slot_id}) and its {{len(_symbols_insert_data_list)}} symbols.")

def downgrade():
    # Use f-strings for slot_id, ensure it's an int for safety if used directly in SQL
    # For op.execute, parameters should ideally be bound, but simple f-string is used here.
    op.execute(f"DELETE FROM slot_symbol WHERE slot_id = {{int({slot_id})}}")
    op.execute(f"DELETE FROM slot WHERE id = {{int({slot_id})}}")
    print(f"Migration {{revision}}: Rolled back slot '{theme_name}' (DB ID: {slot_id}) and its symbols.")

"""
    try:
        with open(migration_filepath, 'w') as f:
            f.write(migration_template)
        print(f"INFO: Successfully generated migration file: {migration_filepath}")
        print(f"  New Revision ID: {new_revision_id}")
        print(f"  Down Revision: {down_revision if down_revision else 'None'}")
    except IOError as e:
        print(f"ERROR: Could not write migration file {migration_filepath}: {e}")


def main():
    """Main function to drive the slot builder script."""
    parser = argparse.ArgumentParser(
        description="SlotBuilder: Automates themed slot game creation.",
        formatter_class=argparse.RawTextHelpFormatter # To allow newlines in help
    )
    parser.add_argument("theme", type=str, help="Theme for the slot game (e.g., 'Mystic Forest').")
    parser.add_argument("--slot_id", type=int, help="Optional DB ID for the new slot game.\nIf not provided, script tries to find the next available ID.")
    parser.add_argument("--cascading", action="store_true", help="Enable cascading feature for this slot.")
    parser.add_argument("--cascade_type", type=str, default=None, help="Type of cascade (e.g., 'fall_from_top', 'replace_in_place').")
    parser.add_argument("--min_match", type=int, default=None, help="Minimum symbols to match for cluster/match-N wins.")
    parser.add_argument("--multipliers", type=str, default="[]", help="JSON string for win multipliers array (e.g., '[1,2,3,5]').")

    args = parser.parse_args()
    theme_name = args.theme
    provided_slot_id = args.slot_id
    # New arguments for cascading features
    is_cascading_arg = args.cascading
    cascade_type_arg = args.cascade_type
    min_symbols_to_match_arg = args.min_match
    win_multipliers_arg_str = args.multipliers

    print(f"--- SlotBuilder Starting for theme: '{theme_name}' ---")

    # Sanitize theme name for use in paths and code names
    # Remove potentially problematic characters, then convert to lowercase snake_case
    sanitized_theme_name = re.sub(r'[^a-zA-Z0-9 _-]', '', theme_name)
    short_name = sanitized_theme_name.lower().replace(' ', '_').replace('-', '_')
    short_name = re.sub(r'[^a-z0-9_]', '', short_name) # Final clean for path/name

    if not short_name:
        print("ERROR: Theme name resulted in empty short_name after sanitization. "
              "Please use a more descriptive and valid theme name (letters, numbers, spaces, underscores, hyphens).")
        return

    # Determine the slot_id for the database entry
    actual_db_slot_id = provided_slot_id if provided_slot_id is not None else get_next_slot_id()
    if actual_db_slot_id is None:
        print("ERROR: Could not determine a valid slot ID. Exiting.")
        return

    # Define paths
    asset_dir_for_config = f"/{short_name}/"
    base_script_dir = os.path.dirname(os.path.abspath(__file__))
    asset_path_for_creation = os.path.join(base_script_dir, "..", "..", "casino_fe", "public", short_name)

    print(f"INFO: Sanitized Short Name: '{short_name}'")
    print(f"INFO: Database Slot ID to be used: {actual_db_slot_id}")
    print(f"INFO: Asset Directory for gameConfig.json references: '{asset_dir_for_config}'")
    print(f"INFO: Full Path for Asset File Creation: '{asset_path_for_creation}'")

    try:
        # Create asset directory if it doesn't exist
        if not os.path.exists(asset_path_for_creation):
            os.makedirs(asset_path_for_creation)
            print(f"INFO: Created asset directory: {asset_path_for_creation}")
        else:
            print(f"INFO: Asset directory {asset_path_for_creation} already exists. Files may be overwritten.")

        # Step 1: Generate placeholder images and get symbol details for config
        symbol_config_details = generate_images(theme_name, short_name, actual_db_slot_id, asset_path_for_creation)
        if not symbol_config_details:
            print("ERROR: Image generation step failed or returned no symbol details. Aborting.")
            return

        # Step 2: Generate gameConfig.json and get DB details for migration
        db_details_from_config = generate_game_config(
            theme_name, short_name, actual_db_slot_id,
            asset_dir_for_config, asset_path_for_creation, symbol_config_details,
            is_cascading_arg, cascade_type_arg, min_symbols_to_match_arg, win_multipliers_arg_str
        )
        if not db_details_from_config:
            print("ERROR: gameConfig.json generation step failed. Aborting.")
            return

        # Step 3: Generate migration file
        generate_migration_file(theme_name, short_name, actual_db_slot_id, asset_dir_for_config, db_details_from_config, symbol_config_details)

        print(f"\n--- SlotBuilder processing for theme '{theme_name}' completed successfully! ---")
        print("\nSummary of created/targeted items:")
        print(f"- Asset directory: {asset_path_for_creation}")
        print(f"  - Placeholder images for background, border, UI, and {len(symbol_config_details)} symbols.")
        print(f"- Game configuration: {os.path.join(asset_path_for_creation, 'gameConfig.json')}")
        migration_output_dir = os.path.abspath(os.path.join(base_script_dir, '..', 'migrations', 'versions'))
        print(f"- Database migration file in: {migration_output_dir}")
        print("\nRecommended Next Steps:")
        print("1. Review all generated files, especially the migration script for correctness against your DB model.")
        print("2. Replace placeholder images in the asset directory with actual themed assets.")
        print("3. Run 'flask db upgrade' (or equivalent Alembic command) to apply the database migration.")
        print("4. Test the new slot game thoroughly.")

    except Exception as e:
        print(f"\nFATAL ERROR: An unexpected error occurred during SlotBuilder execution: {e}")
        print("Please check the console output for details. Script execution halted.")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
