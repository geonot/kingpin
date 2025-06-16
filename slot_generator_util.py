import os
import re
import io
import json
import argparse
from datetime import datetime, timezone
from PIL import Image
import google.generativeai as genai # Retained for structure, though calls are simulated/bypassed
import google.generativeai.types as genai_types # Retained for structure

# Helper function to generate a single image (simulated)
def _generate_single_image(model, prompt: str, output_path: str) -> bool:
    try:
        print(f"SIMULATING image generation for: {os.path.basename(output_path)} with prompt: \"{prompt[:100]}...\"")
        try:
            img = Image.new('RGB', (60, 30), color = 'darkgrey')
            img.save(output_path, "PNG")
            print(f"Successfully SIMULATED and saved placeholder image to {output_path}")
            return True
        except Exception as e_save:
            print(f"Error saving placeholder image {output_path}: {e_save}")
            return False
    except Exception as e:
        print(f"Error (simulated) generating image {output_path}: {e}")
        return False

# Generates a themed list of images (simulated)
def generate_images_for_theme(theme_description: str, images_output_dir: str, model) -> list[str]:
    generated_image_paths = []
    # Using the expanded list of 7 image types
    image_specs = [
        {'filename': 'symbol_10.png', 'prompt_template': "Create a stylized '10' for a {} theme slot reel symbol."},
        {'filename': 'thematic_symbol_1.png', 'prompt_template': "Create a unique thematic symbol for a {} theme slot game."},
        {'filename': 'button_play.png', 'prompt_template': "Create a 'Play' button icon for a {} slot game."},
        {'filename': 'background.png', 'prompt_template': "Create a background for a {} theme slot game."},
        {'filename': 'bonus_background.png', 'prompt_template': "Create a bonus background for a {} theme slot game."},
        {'filename': 'wild_symbol.png', 'prompt_template': "Create a WILD symbol for a {} theme slot game."},
        {'filename': 'scatter_symbol.png', 'prompt_template': "Create a SCATTER symbol for a {} theme slot game."},
    ]
    print(f"Note: Generating a (SIMULATED) set of {len(image_specs)} images for theme '{theme_description}'.")
    for spec in image_specs:
        prompt = spec['prompt_template'].format(theme_description)
        output_path = os.path.join(images_output_dir, spec['filename'])
        if _generate_single_image(model, prompt, output_path):
            generated_image_paths.append(output_path)
        else:
            print(f"Failed to SIMULATE generation for {spec['filename']}.")
    return generated_image_paths

# Main asset generation orchestrator
def generate_slot_assets(theme_description: str, api_key_to_use: str, output_base_dir_val: str = "generated_slots", slot_id_val: int = 0):
    theme_name = theme_description.lower().replace(" ", "_")
    theme_name = re.sub(r'[^a-z0-9_]', '', theme_name)
    if not theme_name:
        print("Error: Could not derive a valid theme name.")
        return

    print(f"Derived theme name: {theme_name}")
    images_dir = os.path.join(output_base_dir_val, theme_name, "images")
    theme_dir = os.path.join(output_base_dir_val, theme_name) # Used for config and migration

    try:
        os.makedirs(images_dir, exist_ok=True)
        print(f"Successfully created/ensured directory: {images_dir}")
    except OSError as e:
        print(f"Error creating directory {images_dir}: {e}")
        return

    model_to_pass = None
    if api_key_to_use and api_key_to_use not in ["SIMULATED_KEY", "NO_KEY_FOUND"]:
        print("Note: Actual genai.configure() and GenerativeModel() calls would happen here if not in full simulation.")
    else:
        print(f"Note: Using placeholder API key ('{api_key_to_use}'); genai configuration skipped.")

    print(f"(Running with slot_id: {slot_id_val} in SIMULATED image generation mode)")
    generated_images = generate_images_for_theme(theme_name, images_dir, model_to_pass)
    if generated_images:
        print(f"\nSuccessfully SIMULATED generation of {len(generated_images)} images.")
    else:
        print("\nNo images were SIMULATED successfully.")

    config_file_path = ""
    if generated_images:
        config_file_path = generate_game_config(theme_description, theme_name, generated_images, theme_dir, slot_id_val)
        if config_file_path:
            print(f"Game config file generated at: {config_file_path}")
        else:
            print("Failed to generate game config file.")
    else:
        print("Skipping game config generation as no images were generated.")

    if config_file_path:
        migration_script_path = generate_migration_script(theme_name, config_file_path, theme_dir)
        if migration_script_path:
            print(f"Migration script generated at: {migration_script_path}")
        else:
            print("Failed to generate migration script.")
    else:
        print("Skipping migration script generation as game config was not generated or failed.")

    print(f"\nAsset generation process for '{theme_description}' (theme: '{theme_name}') completed in '{output_base_dir_val}'.")

# Helper to find image paths for config
def _find_image_path(filename_to_find: str, generated_image_paths: list[str], theme_name: str) -> str:
    base_asset_path = f"/slots/{theme_name}/images/"
    for path in generated_image_paths:
        if os.path.basename(path) == filename_to_find:
            return base_asset_path + filename_to_find
    print(f"Warning: Image '{filename_to_find}' not found in generated paths. Using placeholder path: {base_asset_path + filename_to_find}")
    return base_asset_path + filename_to_find

# **Restored generate_game_config function**
def generate_game_config(theme_description: str, theme_name: str, generated_image_paths: list[str], config_output_dir: str, slot_id_val: int = 0) -> str:
    config = {
        "game": {
            "slot_id": slot_id_val,
            "name": f"{theme_description.title()} Slots",
            "short_name": theme_name,
            "asset_dir": f"/slots/{theme_name}/",
            "layout": {'rows': 3, 'columns': 5},
            "symbols": [],
            "symbol_count": 0,
            "symbol_scatter": None,
            "symbol_wild": None,
            "paylines": [
                [[0,0],[1,0],[2,0],[3,0],[4,0]], [[0,1],[1,1],[2,1],[3,1],[4,1]], [[0,2],[1,2],[2,2],[3,2],[4,2]],
                [[0,0],[1,1],[2,2],[3,1],[4,0]], [[0,2],[1,1],[2,0],[3,1],[4,2]],
                # Adding a few more for variety
                [[0,0],[0,1],[0,2],[0,3],[0,4]], [[1,0],[1,1],[1,2],[1,3],[1,4]], [[2,0],[2,1],[2,2],[2,3],[2,4]],
                [[0,0],[1,1],[2,0],[1,1],[0,0]], [[2,2],[1,1],[0,2],[1,1],[2,2]]
            ],
            "payouts": [],
            "ui": {
                "buttons": {
                    "spin": {"icon": _find_image_path("button_play.png", generated_image_paths, theme_name), "position": [0,0], "action": "spin"},
                    "autoSpin": {"icon": _find_image_path("button_autoplay.png", generated_image_paths, theme_name), "position": [0,0], "action": "autoSpin"}, # Expected, might be missing
                    "settings": {"icon": _find_image_path("button_settings.png", generated_image_paths, theme_name), "position": [0,0], "action": "settings"}, # Expected, might be missing
                    "betAdjust": {
                        "plus": {"icon": _find_image_path("button_bet_plus.png", generated_image_paths, theme_name), "position": [0,0], "action": "increaseBet"}, # Expected, might be missing
                        "minus": {"icon": _find_image_path("button_bet_minus.png", generated_image_paths, theme_name), "position": [0,0], "action": "decreaseBet"} # Expected, might be missing
                    },
                    "stop": {"icon": _find_image_path("button_stop.png", generated_image_paths, theme_name), "position": [0,0], "action": "stopSpin"}, # Expected, might be missing
                },
                "text_fields": {
                    "balance": {"font": "Arial", "size": 16, "color": "#FFFFFF", "position": [100, 50]},
                    "bet": {"font": "Arial", "size": 16, "color": "#FFFFFF", "position": [200, 50]},
                    "win": {"font": "Arial", "size": 16, "color": "#FFFF00", "position": [300, 50]}
                }
            },
            "reel": { "spin_duration": 1.0, "stop_delay": 0.2, "bounce_height": 50, "bounce_duration": 0.3 },
            "background": { "image": _find_image_path("background.png", generated_image_paths, theme_name), "color": "#000000" },
            "animations": { "win_line_highlight": {"type": "glow", "color": "#FFFF00", "duration": 0.5}, "symbol_win_effect": {"type": "pulse", "scale": 1.2, "duration": 0.3} },
            "bonus": {
                "bonusGameEntry": "SCATTER_TRIGGER", "bonusType": "FREE_SPINS", "freeSpinsCount": 10, "bonusMultiplier": 1,
                "bonusBackgroundAsset": _find_image_path("bonus_background.png", generated_image_paths, theme_name),
                "bonusMusic": f"/slots/{theme_name}/sounds/bonus_music.mp3"
            },
            "sound": {
                "masterVolume":0.8, "musicVolume":0.5, "sfxVolume":1.0,
                "backgroundMusic": f"/slots/{theme_name}/sounds/background_music.mp3",
                "effects": { "spin": f"/slots/{theme_name}/sounds/spin.wav", "reelStop": f"/slots/{theme_name}/sounds/reel_stop.wav", "winSmall": f"/slots/{theme_name}/sounds/win_small.wav"}
            },
            "settings": {
                "volume_control": True, "sound_toggle": True, "history_available": True,
                "betOptions": [0.10, 0.20, 0.50, 1.00, 2.00, 5.00]
            }
        }
    }
    symbol_id_counter = 1
    symbol_payouts = []
    symbol_value_map = {"10":1.0, "j":1.2,"q":1.4,"k":1.6,"a":2.0, "thematic_symbol_1":3.0, "wild":0, "scatter":0, "coin":0}

    for img_path in generated_image_paths:
        filename = os.path.basename(img_path)
        icon_path = f"/slots/{theme_name}/images/{filename}"
        name_part = filename.lower().replace(".png", "").replace("symbol_", "")

        symbol_data = {"id": symbol_id_counter, "icon": icon_path, "name": name_part.replace("_", " ").title(), "value": 0}
        is_processed_symbol = False

        if "wild_symbol" == name_part:
            symbol_data["name"] = "Wild"
            config["game"]["symbol_wild"] = symbol_id_counter
            is_processed_symbol = True
        elif "scatter_symbol" == name_part:
            symbol_data["name"] = "Scatter"
            config["game"]["symbol_scatter"] = symbol_id_counter
            is_processed_symbol = True
        elif "coin_symbol" == name_part: # Assuming coin_symbol.png might exist
            symbol_data["name"] = "Coin"
            symbol_data["isBonusCoin"] = True
            is_processed_symbol = True
        elif name_part in symbol_value_map: # For 10, J, Q, K, A, thematic_symbol_1
            symbol_data["name"] = name_part.replace("_", " ").title()
            symbol_data["value"] = symbol_value_map[name_part]
            is_processed_symbol = True
        elif name_part.startswith("thematic_symbol_"): # Generic thematic if more exist
             symbol_data["name"] = name_part.replace("_", " ").title()
             symbol_data["value"] = symbol_value_map.get(name_part, 3.5) # Default thematic value
             is_processed_symbol = True

        if is_processed_symbol:
            config["game"]["symbols"].append(symbol_data)
            if symbol_data["value"] > 0:
                 symbol_payouts.append({"symbol_id": symbol_id_counter, "matches": 3, "multiplier": symbol_data["value"] * 0.5})
                 symbol_payouts.append({"symbol_id": symbol_id_counter, "matches": 4, "multiplier": symbol_data["value"] * 1.0})
                 symbol_payouts.append({"symbol_id": symbol_id_counter, "matches": 5, "multiplier": symbol_data["value"] * 2.0})
            symbol_id_counter += 1

    config["game"]["symbol_count"] = len(config["game"]["symbols"])
    config["game"]["payouts"] = symbol_payouts

    output_filepath = os.path.join(config_output_dir, "gameConfig.json")
    try:
        with open(output_filepath, 'w') as f: json.dump(config, f, indent=2)
        print(f"Successfully generated gameConfig.json at {output_filepath}")
    except IOError as e:
        print(f"Error writing gameConfig.json: {e}"); return ""
    return output_filepath

# **Restored generate_migration_script function**
def generate_migration_script(theme_name: str, game_config_path: str, migration_output_dir: str) -> str:
    try:
        with open(game_config_path, 'r') as f:
            game_config_data = json.load(f)['game']
    except (IOError, json.JSONDecodeError, KeyError) as e:
        print(f"Error reading or parsing gameConfig.json: {e}")
        return ""

    try:
        slot_id = game_config_data.get('slot_id', 0)
        slot_name = game_config_data.get('name', f"{theme_name.title()} Slots")
        layout = game_config_data.get('layout', {'rows': 3, 'columns': 5})
        num_rows = layout.get('rows', 3)
        num_columns = layout.get('columns', 5)
        num_symbols = game_config_data.get('symbol_count', 0)
        wild_symbol_id = game_config_data.get('symbol_wild') # Can be None
        scatter_symbol_id = game_config_data.get('symbol_scatter') # Can be None
        short_name = game_config_data.get('short_name', theme_name)
        asset_directory = game_config_data.get('asset_dir', f"/slots/{theme_name}/")
        paylines = game_config_data.get('paylines', [])
        payouts = game_config_data.get('payouts', [])
        symbols_data = game_config_data.get('symbols', [])
        settings_data = game_config_data.get('settings', {})
        bet_options = settings_data.get('betOptions', [0.1, 0.2, 0.5, 1.0, 2.0])
        bonus_data = game_config_data.get('bonus', {})
        bonus_type = bonus_data.get('bonusType', 'FREE_SPINS')
    except Exception as e:
        print(f"Error extracting data from game_config_data: {e}")
        return ""

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    revision_id = f"add_{theme_name}_slot_{timestamp}"
    utc_now_iso = datetime.now(timezone.utc).isoformat()

    reel_configurations_json_str = json.dumps({'paylines': paylines, 'payouts': payouts})

    slot_table_data = [{
        'id': slot_id, 'name': slot_name, 'short_name': short_name,
        'asset_directory': asset_directory, 'num_rows': num_rows, 'num_columns': num_columns,
        'num_symbols': num_symbols,
        'wild_symbol_id': wild_symbol_id if wild_symbol_id is not None else sa.null(),
        'scatter_symbol_id': scatter_symbol_id if scatter_symbol_id is not None else sa.null(),
        'rtp': 96.0, 'volatility': 'medium',
        'reel_configurations': reel_configurations_json_str, # Already a JSON string
        'bonus_type': bonus_type,
        'is_active': True, 'created_at': utc_now_iso, 'updated_at': utc_now_iso,
    }]

    slot_symbol_table_data = []
    if symbols_data: # Ensure symbols_data is not empty
        for s in symbols_data:
            slot_symbol_table_data.append({
                'slot_id': slot_id, 'symbol_id': s['id'], 'name': s['name'], 'value': s.get('value',0), # Ensure value exists
                'icon_path': s['icon'],
                'is_wild': s['id'] == wild_symbol_id if wild_symbol_id is not None else False,
                'is_scatter': s['id'] == scatter_symbol_id if scatter_symbol_id is not None else False,
                'is_bonus_coin': s.get('isBonusCoin', False), 'created_at': utc_now_iso,
            })

    slot_bet_table_data = []
    if bet_options: # Ensure bet_options is not empty
        for val in bet_options:
            slot_bet_table_data.append({
                'slot_id': slot_id, 'bet_amount': val,
                'is_default': val == bet_options[0],
                'created_at': utc_now_iso,
            })

    # Using json.dumps for the data lists to embed them as Python literal strings in the script
    # This is safer than complex f-string interpolation for nested structures.
    script_content = f\"\"\"\"\"\"add {theme_name} slot game data, rev: {revision_id}\"\"\"
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql # Assuming PostgreSQL
import datetime
import json

revision = '{revision_id}'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    slot_table = sa.table('slot_table',
        sa.column('id', sa.Integer), sa.column('name', sa.String), sa.column('short_name', sa.String),
        sa.column('asset_directory', sa.String), sa.column('num_rows', sa.Integer), sa.column('num_columns', sa.Integer),
        sa.column('num_symbols', sa.Integer), sa.column('wild_symbol_id', sa.Integer), sa.column('scatter_symbol_id', sa.Integer),
        sa.column('rtp', sa.Float), sa.column('volatility', sa.String), sa.column('reel_configurations', postgresql.JSONB),
        sa.column('bonus_type', sa.String), sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime(timezone=True)), sa.column('updated_at', sa.DateTime(timezone=True))
    )
    slot_symbol_table = sa.table('slot_symbol_table',
        sa.column('slot_id', sa.Integer), sa.column('symbol_id', sa.Integer), sa.column('name', sa.String),
        sa.column('value', sa.Float), sa.column('icon_path', sa.String), sa.column('is_wild', sa.Boolean),
        sa.column('is_scatter', sa.Boolean), sa.column('is_bonus_coin', sa.Boolean),
        sa.column('created_at', sa.DateTime(timezone=True))
    )
    slot_bet_table = sa.table('slot_bet_table',
        sa.column('slot_id', sa.Integer), sa.column('bet_amount', sa.Numeric(precision=10, scale=2)),
        sa.column('is_default', sa.Boolean), sa.column('created_at', sa.DateTime(timezone=True))
    )

    # Data for bulk insert (datetime strings will be handled by SQLAlchemy)
    slot_data = json.loads('{json.dumps(slot_table_data)}')
    symbol_data = json.loads('{json.dumps(slot_symbol_table_data)}')
    bet_data = json.loads('{json.dumps(slot_bet_table_data)}')

    op.bulk_insert(slot_table, slot_data)
    if symbol_data: # Only insert if not empty
        op.bulk_insert(slot_symbol_table, symbol_data)
    if bet_data: # Only insert if not empty
        op.bulk_insert(slot_bet_table, bet_data)

def downgrade():
    # Using short_name to identify the slot to remove.
    op.execute(f"DELETE FROM slot_bet_table WHERE slot_id IN (SELECT id FROM slot_table WHERE short_name = '{short_name}')")
    op.execute(f"DELETE FROM slot_symbol_table WHERE slot_id IN (SELECT id FROM slot_table WHERE short_name = '{short_name}')")
    op.execute(f"DELETE FROM slot_table WHERE short_name = '{short_name}'")
\"\"\"
    filename = f"{timestamp}_add_{theme_name}_slot.py"
    output_filepath = os.path.join(migration_output_dir, filename)
    try:
        os.makedirs(migration_output_dir, exist_ok=True)
        with open(output_filepath, 'w') as f:
            f.write(script_content)
        print(f"Successfully generated migration script: {output_filepath}")
    except IOError as e:
        print(f"Error writing migration script: {e}")
        return ""
    return output_filepath

# Argparse and main execution
def main():
    parser = argparse.ArgumentParser(description="Slot Theme Asset Generator Utility.")
    parser.add_argument("theme_description", help="Textual description of the slot game theme (e.g., 'Jungle Adventure').")
    parser.add_argument("--output_base_dir", default="generated_slots", help="Base directory for output. Default: 'generated_slots'.")
    parser.add_argument("--api_key", default=None, help="Gemini API key. If not provided, tries GEMINI_API_KEY environment variable.")
    parser.add_argument("--slot_id", type=int, default=0, help="Placeholder Slot ID to use. Default: 0.")

    args = parser.parse_args()
    actual_api_key = args.api_key if args.api_key else os.getenv("GEMINI_API_KEY")

    if not actual_api_key:
        print("Warning: API key not provided. Proceeding in simulation mode with placeholder key.")
        actual_api_key = "SIMULATED_KEY"

    print(f"Starting asset generation for theme: '{args.theme_description}'")
    try:
        generate_slot_assets(
            theme_description=args.theme_description,
            api_key_to_use=actual_api_key,
            output_base_dir_val=args.output_base_dir,
            slot_id_val=args.slot_id
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
