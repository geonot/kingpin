# Slot Theme Asset Generator Utility

## 1. Purpose

This utility generates a set of assets for a new slot game based on a provided theme description. It creates:
- Placeholder image files for standard symbols, thematic symbols, special symbols (WILD, SCATTER, COIN), UI buttons, and backgrounds. (Actual image generation via Google Gemini API is currently simulated).
- A `gameConfig.json` file detailing the game's configuration, symbols, paylines, UI layout, etc.
- An Alembic/SQLAlchemy database migration script for PostgreSQL to add the new slot game's data to the database.

The generated files are organized into a directory named after the processed theme.

## 2. Requirements

- Python 3.7+
- Pillow library (`pip install Pillow`)
- Google Generative AI library (`pip install google-generativeai`)
- A valid Google Gemini API Key for actual image generation.

## 3. Setup

### Gemini API Key
To enable actual image generation (currently simulated in the script):
1. Obtain a Gemini API Key from Google AI Studio.
2. You can provide the API key in one of two ways:
   - **Command-line argument:** Use the `--api_key YOUR_API_KEY` option when running the script.
   - **Environment variable:** Set the `GEMINI_API_KEY` environment variable:
     ```bash
     export GEMINI_API_KEY="YOUR_API_KEY_HERE"
     ```

## 4. Usage

Run the script from the command line using `python slot_generator_util.py`:

```bash
python slot_generator_util.py "Your Theme Description Here" [OPTIONS]
```

### Arguments:
- **`theme_description`** (required): A textual description of the slot game theme (e.g., "Ancient Egypt Treasures", "Sci-Fi Robots Attack"). This will be used for directory naming and in prompts for image generation.

### Options:
- **`--output_base_dir DIRECTORY`**: Specifies the base directory where the theme-specific output folder will be created. Defaults to `"generated_slots"`.
  Example: `--output_base_dir my_slot_projects`
- **`--api_key YOUR_API_KEY`**: Your Google Gemini API key. Overrides the environment variable if set.
- **`--slot_id ID`**: A placeholder Slot ID (integer) to use in the generated `gameConfig.json` and migration script. Defaults to `0`.
  Example: `--slot_id 101`

### Example Command:
```bash
python slot_generator_util.py "Mystical Dragon's Hoard" --output_base_dir ./slot_builds --slot_id 5 --api_key YOUR_ACTUAL_API_KEY
```

## 5. Input

- **Theme Description**: A string describing the desired theme. This influences the (simulated) image prompts and naming conventions. Keep it concise but descriptive.

## 6. Output

The utility creates a new directory structure: `<output_base_dir>/<processed_theme_name>/`.
For example, if `output_base_dir` is `generated_slots` and the theme is "Jungle Adventure", it creates `generated_slots/jungle_adventure/`.

Inside this directory, you will find:
- **`images/`**: Contains the generated (currently placeholder) PNG image files.
  - `symbol_10.png`, `symbol_j.png`, etc.
  - `thematic_symbol_1.png`, etc.
  - `wild_symbol.png`, `scatter_symbol.png`, `coin_symbol.png`
  - `background.png`, `bonus_background.png`
  - `button_play.png`, `button_settings.png`, etc.
- **`gameConfig.json`**: The main configuration file for the slot game, structured in JSON format. Includes paths to the generated images.
- **`<timestamp>_add_<theme_name>_slot.py`**: The database migration script.

## 7. Simulation Mode (Current Status)

**Important:** The current version of `slot_generator_util.py` **simulates** image generation. Instead of calling the Google Gemini API, it creates simple placeholder PNG files.

To enable **actual image generation**:
1. Ensure you have a valid Gemini API key set up (see Section 3).
2. In `slot_generator_util.py`, locate the `generate_slot_assets` function.
3. Uncomment the lines related to `genai.configure(api_key=api_key_to_use)` and `model_to_pass = genai.GenerativeModel(...)`.
4. In the `_generate_single_image` function, replace the Pillow placeholder image creation logic with the actual `model.generate_content(...)` call and image processing logic (refer to the initial Gemini API Python snippet provided in the issue).

The script will still function and generate the config and migration files when in simulation mode, using the placeholder images.

## 8. Customization

The generated `gameConfig.json` and migration script are intended as **starting points**. You will likely need to customize them:
- **`gameConfig.json`**:
    - Review and adjust symbol values, payouts, paylines.
    - Fine-tune UI element positions and styles.
    - Update animation and sound settings.
    - Modify bonus game parameters.
- **Migration Script (`*_add_<theme_name>_slot.py`)**:
    - Update the `down_revision` variable to point to the actual previous migration ID in your Alembic setup.
    - The `slot_id` used in the script is based on the `--slot_id` argument (default 0). Ensure this ID is unique and appropriate for your database before applying the migration.
    - Review default values for RTP, volatility, etc., in the `slot_table` insertion.

This utility aims to bootstrap the initial asset creation process, not to produce a production-ready game out of the box.
