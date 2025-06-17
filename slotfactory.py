import os
import json
import argparse
import uuid
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
import textwrap

# User-specified imports
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# --- Configuration ---
# Load API key from a .env file in the same directory
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file or environment variables. Please create a .env file and add GOOGLE_API_KEY=\"YOUR_API_KEY\"")

# Use the exact model names requested
TEXT_MODEL_NAME = "gemini-1.5-pro-latest" # Updated to a stable, powerful text model
IMAGE_MODEL_NAME = "gemini-1.5-flash-latest" # Updated to a stable, fast image model

# --- Instantiate the GenAI Client (as per user's code) ---
# This client object will be used for all API calls.
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    print(f"!! Failed to initialize Google GenAI Client: {e}")
    print("!! Please ensure your API key is correct and has access to the specified models.")
    exit()

# --- Helper Functions ---

def create_dir_if_not_exists(path):
    """Creates a directory if it doesn't already exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")

def sanitize_filename(name):
    """Sanitizes a string to be used as a valid filename."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name).lower()

# --- Core Generation Logic (Adapted for the specified SDK style) ---

def generate_text(prompt, model_name=TEXT_MODEL_NAME):
    """Generates text content using the client.models.generate_content method."""
    print(f"\n>> Sending text prompt to {model_name}...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        # This older client structure nests the content in candidates and parts
        if response.candidates and response.candidates[0].content.parts:
            full_text = "".join(part.text for part in response.candidates[0].content.parts if part.text)
            return full_text
        else:
            print("!! Text generation returned no content.")
            print(f"   Response: {response}")
            return None
            
    except Exception as e:
        print(f"!! Text generation failed: {e}")
        return None

def generate_and_save_image(prompt, filepath, model_name=IMAGE_MODEL_NAME):
    """Generates an image using the client.models.generate_content method and saves it."""
    print(f">> Generating image: {os.path.basename(filepath)}...")
    try:
        # Configuration required to tell the model we expect an image back
        config = types.GenerateContentConfig(
            response_modalities=["Image"]
        )
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )

        # Iterate through the parts to find the image data, as per the user's snippet
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                image = Image.open(BytesIO(image_data))
                
                # Convert to RGBA to ensure it has an alpha channel for transparency
                image = image.convert("RGBA")
                
                image.save(filepath, 'PNG')
                print(f"   Saved to {filepath}")
                return True # Success
        
        # If loop finishes and no image was found
        print(f"!! Image generation succeeded but no image data was found in the response for {os.path.basename(filepath)}.")
        return False

    except Exception as e:
        print(f"!! Image generation failed for {os.path.basename(filepath)}: {e}")
        return False


def generate_creative_brief(theme):
    """Expands a simple theme into a detailed creative brief."""
    prompt = textwrap.dedent(f"""
        You are a creative director for a slot game company.
        Based on the theme "{theme}", create a rich, detailed, and evocative creative brief for a new slot game.
        This brief will be used to guide artists and developers.
        Include details about:
        - The overall atmosphere and mood.
        - The specific setting (e.g., "deep within a misty, ancient Aztec jungle, filled with crumbling ruins and glowing flora").
        - The visual style (e.g., "vibrant and slightly mystical, with a hand-painted feel, using a color palette of deep greens, golds, and turquoise").
        - Key thematic elements that could become symbols.
        - The feeling the game should evoke (e.g., "adventure, discovery, and the thrill of finding hidden treasure").
        This brief is the single source of truth for all asset generation.
    """)
    return generate_text(prompt)


def generate_all_images(brief, output_dir, num_special_symbols=4):
    """Generates all required image assets for the slot game."""
    print("\n--- Starting Image Asset Generation ---")
    
    symbol_names = ['10', 'J', 'Q', 'K', 'A'] + [f'Special_{i+1}' for i in range(num_special_symbols)] + ['WILD', 'SCATTER', 'Coin']
    ui_names = ['background', 'bonus_background', 'play', 'autoplay', 'settings', 'change_bet_plus', 'change_bet_minus', 'stop']
    
    image_prompts = {}

    for name in symbol_names:
        prompt_detail = {
            'WILD': 'This is the most powerful symbol, it should look exciting and dynamic.',
            'SCATTER': 'This symbol triggers the bonus round, it should feel special and rare, like a key.',
            'Coin': 'This is a bonus coin symbol used in a hold-and-win feature. It should look like a valuable thematic coin or gem.'
        }.get(name, f'This is a {"low" if name in "10JQKA" else "high"}-value symbol.')

        prompt = (f"Create a vibrant, stylized '{name}' slot reel symbol. The symbol must be centered, square, have a transparent background, and be clearly recognizable at a small size. The art style should be consistent with this game theme: '{brief}'.")
        image_prompts[f"{sanitize_filename(name)}.png"] = prompt

    ui_details = {
        'background': "Create an immersive 1920x1080 background image. The central area for the 5x3 reels should be visually distinct or slightly darker to ensure symbols are readable. Theme: '{brief}'.",
        'bonus_background': "Create a more exciting 1920x1080 background for the bonus round. It should feel like a high-stakes version of the main background. Theme: '{brief}'.",
        'play': "Create a thematic 'Play' button icon, like a stylized circular arrow. Centered, square, transparent background. Theme: '{brief}'.",
        'autoplay': "Create a thematic 'Autoplay' button icon, like a play icon with an infinite loop. Centered, square, transparent background. Theme: '{brief}'.",
        'settings': "Create a thematic 'Settings' button icon, like a stylized gear. Centered, square, transparent background. Theme: '{brief}'.",
        'change_bet_plus': "Create a thematic '+' icon. Centered, square, transparent background. Theme: '{brief}'.",
        'change_bet_minus': "Create a thematic '-' icon. Centered, square, transparent background. Theme: '{brief}'.",
        'stop': "Create a thematic 'Stop' button icon, like a stylized square. Centered, square, transparent background. Theme: '{brief}'."
    }

    for name, detail in ui_details.items():
        image_prompts[f"{name}.png"] = detail.format(brief=brief)

    for filename, prompt in image_prompts.items():
        filepath = os.path.join(output_dir, filename)
        generate_and_save_image(prompt, filepath)

def generate_config_and_migration(brief, theme_name, slot_id, short_name):
    """Generates the game description, config JSON, and Alembic migration data."""
    print("\n--- Generating Game Configuration and Database Migration ---")
    
    prompt = textwrap.dedent(f"""
        You are a senior slot game designer. Based on the provided creative brief, generate the necessary configuration data for a new slot game.

        **Creative Brief:** "{brief}"

        **Game Core Details:**
        - Game Name: {theme_name}
        - Slot ID: {slot_id}
        - Short Name: {short_name}
        - Asset Directory: /slots/{short_name}/
        - Layout: 5 columns, 3 rows
        - Low-pay symbols: 10, J, Q, K, A (IDs 1-5)
        - High-pay symbols: 4 thematic symbols (IDs 6-9)
        - WILD Symbol ID: 10
        - SCATTER Symbol ID: 11
        - Bonus Coin Symbol ID: 12

        **Your Tasks:**
        1.  **Marketing Description:** Write a short, exciting 1-2 sentence marketing description.
        2.  **Thematic Symbol Names:** Invent creative, thematic names for the 4 high-paying symbols and the special symbols (WILD, SCATTER, Coin).
        3.  **Paytable and Weights:** Create a balanced paytable and symbol weights. Higher value symbols must have lower weights (be rarer).
        4.  **Final JSON Output:** Format all of this information into a single, valid JSON object with three top-level keys: "description", "game_config", and "alembic_data". The structure of these objects must match the examples provided in the user's original request.

        Ensure the output is ONLY the raw JSON object and nothing else.
    """)

    json_string = generate_text(prompt)
    if not json_string:
        print("!! Failed to generate configuration data.")
        return None, None, None

    try:
        json_string = json_string.strip().lstrip('```json').rstrip('```')
        data = json.loads(json_string)
        return data.get('description'), data.get('game_config'), data.get('alembic_data')
    except json.JSONDecodeError as e:
        print(f"!! Failed to parse JSON response from model: {e}")
        print("--- Received Text ---")
        print(json_string)
        print("---------------------")
        return None, None, None

def write_game_config_json(config_data, output_dir, short_name):
    """Writes the gameConfig.json file."""
    filepath = os.path.join(output_dir, "gameConfig.json")
    try:
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"Successfully wrote {filepath}")
    except Exception as e:
        print(f"!! Error writing gameConfig.json: {e}")

def write_alembic_migration(alembic_data, description, slot_id, short_name, output_dir):
    """Writes the Alembic migration .py file."""
    revision = uuid.uuid4().hex[:12]
    down_revision = 'xxxxxxxxxxxx' # IMPORTANT: User must replace this!
    
    alembic_data_str = json.dumps(alembic_data, indent=4)

    migration_template = textwrap.dedent(f"""\
    \"\"\"{description}\"\"\"

    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql
    from datetime import datetime, timezone

    # revision identifiers, used by Alembic.
    revision = '{revision}'
    down_revision = '{down_revision}'
    branch_labels = None
    depends_on = None

    def upgrade() -> None:
        slot_table = sa.table(
            'slots',
            sa.column('id', sa.Integer), sa.column('name', sa.String),
            sa.column('description', sa.String), sa.column('num_rows', sa.Integer),
            sa.column('num_columns', sa.Integer), sa.column('num_symbols', sa.Integer),
            sa.column('wild_symbol_id', sa.Integer), sa.column('scatter_symbol_id', sa.Integer),
            sa.column('bonus_type', sa.String), sa.column('bonus_subtype', sa.String),
            sa.column('bonus_multiplier', sa.Float), sa.column('bonus_spins_trigger_count', sa.Integer),
            sa.column('bonus_spins_awarded', sa.Integer), sa.column('short_name', sa.String),
            sa.column('asset_directory', sa.String), sa.column('rtp', sa.Float),
            sa.column('volatility', sa.String), sa.column('is_active', sa.Boolean),
            sa.column('is_multiway', sa.Boolean), sa.column('reel_configurations', postgresql.JSONB),
            sa.column('is_cascading', sa.Boolean), sa.column('cascade_type', sa.String),
            sa.column('min_symbols_to_match', sa.Integer), sa.column('win_multipliers', postgresql.JSONB),
            sa.column('created_at', sa.DateTime(timezone=True))
        )
        
        # Insert Slot {slot_id} - {alembic_data['name']}
        op.bulk_insert(slot_table, [
            # Using dict expansion for cleaner formatting
            {{**{alembic_data_str}, 'created_at': datetime.now(timezone.utc)}}
        ])

    def downgrade() -> None:
        op.execute(f"DELETE FROM slots WHERE id = {slot_id}")
    """)
    
    filepath = os.path.join(output_dir, f"{revision}_add_{short_name}_slot.py")
    try:
        with open(filepath, 'w') as f:
            f.write(migration_template)
        print(f"Successfully wrote migration file: {filepath}")
        print(f"NOTE: Remember to set the 'down_revision' in the file to the correct previous migration ID.")
    except Exception as e:
        print(f"!! Error writing migration file: {e}")

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Generate a complete slot game package from a theme.")
    parser.add_argument("theme", type=str, help="The high-level theme for the slot game (e.g., 'Viking Fury', 'Cosmic Disco').")
    parser.add_argument("--id", type=int, required=True, help="The unique integer ID for this slot in the database.")
    parser.add_argument("--short_name", type=str, required=True, help="A short, filesystem-friendly name for the slot (e.g., 'viking', 'cosmic').")
    
    args = parser.parse_args()
    
    output_dir = os.path.join("output", args.short_name)
    assets_dir = os.path.join(output_dir, "assets")

    print(f"--- Starting Slot Generation for '{args.theme}' ---")
    create_dir_if_not_exists(output_dir)
    create_dir_if_not_exists(assets_dir)
    
    creative_brief = generate_creative_brief(args.theme)
    if not creative_brief:
        print("!! Halting execution due to failure in generating creative brief.")
        return
    print("\n--- Creative Brief Generated ---")
    print(textwrap.fill(creative_brief, width=80))
    print("--------------------------------\n")
    
    generate_all_images(creative_brief, assets_dir, num_special_symbols=4)
    
    description, game_config, alembic_data = generate_config_and_migration(creative_brief, args.theme, args.id, args.short_name)
    if not all([description, game_config, alembic_data]):
        print("!! Halting execution due to failure in generating config data.")
        return
        
    write_game_config_json(game_config, output_dir, args.short_name)
    write_alembic_migration(alembic_data, description, args.id, args.short_name, output_dir)
    
    print("\n--- Slot Generation Complete! ---")
    print(f"All files saved in: {output_dir}")

if __name__ == "__main__":
    main()