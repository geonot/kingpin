# Slot Game Asset Specifications

This document outlines the specifications for assets required for the new Phaser slot game system. Adhering to these guidelines will ensure visual consistency, optimal performance, and compatibility with the game's features.

## I. General Guidelines

*   **File Formats:**
    *   Images: PNG (with transparency where needed, e.g., symbols, UI buttons). Consider SVG for UI elements if feasible for scalability.
    *   Sounds: MP3 (for background music, longer effects) and WAV (for short, crisp sound effects like button clicks, reel stops).
*   **Resolution & DPI:**
    *   Target a baseline HD resolution (e.g., 1920x1080 landscape).
    *   Provide assets at @1x and @2x scales to support high DPI (Retina) displays. For example, if a symbol's base size in-game is 100x100px, provide a 100x100px PNG (@1x) and a 200x200px PNG (@2x). The game engine will select the appropriate asset.
*   **Naming Conventions:** Use clear, consistent naming conventions (e.g., `symbol_wild.png`, `symbol_wild@2x.png`, `button_spin.png`, `sfx_reel_stop.wav`).
*   **Optimization:** Optimize all assets for web (e.g., using image compression tools like TinyPNG, ensuring audio files are not excessively large).

## II. Symbol Assets

*   **Base Size:** While the game engine will dynamically scale symbols, design them based on an approximate base size (e.g., 150x150 pixels for @1x) to ensure clarity.
*   **Aspect Ratio:** Typically square (1:1). If non-square symbols are used, this must be consistent and noted in the `gameConfig.json`.
*   **Visual Style:**
    *   Symbols should be easily distinguishable.
    *   High contrast against various backgrounds.
    *   "Pop" factor: vibrant, well-defined, and appealing.
*   **States (for potential future animated symbols):**
    *   **Idle:** Standard appearance on the reels.
    *   **Win Animation (Optional Spritesheet):** If a symbol has a unique win animation (beyond standard pulse/shake):
        *   Format: PNG spritesheet.
        *   Provide dimensions (width, height, frame count, frames per row).
        *   Specify animation speed (frames per second).
        *   Example: `symbol_pharaoh_win_spritesheet.png`, `symbol_pharaoh_win.json` (data file for frame definitions if not inferable).
    *   **Anticipation Animation (Optional Spritesheet):** For special symbols (Scatter, Bonus) about to land.
        *   Similar specifications to win animation.
    *   **Configuration in `gameConfig.json` for Win Animations:**
        *   The `gameConfig.json` for each symbol can specify an `animations.win` object within the symbol's definition. This object controls the standard win animation applied by `ModernSlotScene.js`.
        *   Example configurations:
            *   Pulse (default): `{"type": "pulse", "scale": 1.25, "duration": 300}`
            *   Shake: `{"type": "shake", "strength": 5, "duration": 400}` (strength is a pixel offset, duration is for the full shake sequence).
        *   `ModernSlotScene.js` currently supports 'pulse' and 'shake' types. If a symbol has a dedicated spritesheet animation, that would typically be handled differently (e.g., by playing a specific animation key instead of these generic types).
*   **Required Symbols (Standard Set - can be expanded by theme):**
    *   Low-value symbols (e.g., 10, J, Q, K, A or thematic equivalents)
    *   Mid-value symbols (thematic)
    *   High-value symbols (thematic, characters, main objects)
    *   Wild symbol
    *   Scatter symbol
    *   Bonus symbol (if applicable for specific bonus types like Hold & Win)

## III. Background Assets

*   **Main Game Background (`bg.png`):**
    *   Resolution: Minimum 1920x1080px. Consider higher for future-proofing (e.g., 2560x1440px).
    *   Design to be visually interesting but not distracting from the reels.
    *   The central area where reels appear might need to be slightly darker or have less detail to ensure symbol readability.
    *   Must be able to accommodate different aspect ratios gracefully (e.g., by showing more of the sides or being cropped slightly without losing key elements).
*   **Bonus Round Background (`bbg.png`):**
    *   Similar specifications to the main background.
    *   Should feel more exciting or visually distinct to signify the bonus mode.

## IV. UI Element Assets

*   **General:**
    *   Style: Modern, sleek, and consistent with the overall game theme.
    *   Clarity: Buttons should be easily recognizable and their function clear.
    *   Provide states: normal, hover, pressed/active, disabled. (e.g., `button_spin_normal.png`, `button_spin_hover.png`).
    *   **Note on Responsiveness:** While detailed responsive behavior for `ModernUIScene.js` is still evolving, UI assets should be designed to be scalable and clear. Consider providing button assets as individual, clean icons that can be placed onto styled base button surfaces by the scene, or as complete buttons that can scale well and maintain legibility.
*   **Buttons (Examples - exact list may vary per theme config):**
    *   Spin Button
    *   Auto-Spin Button
    *   Turbo Mode Button
    *   Settings Button
    *   Bet Increase (+) Button
    *   Bet Decrease (-) Button
    *   Max Bet Button
    *   Paytable/Info Button
    *   Close Button (for modals)
*   **Other UI Elements:**
    *   **Reel Frame/Border:** An image to frame the reel area, enhancing thematic integration.
    *   **Paytable Background:** Background for the information screens.
    *   **Modal/Popup Backgrounds:** For settings, messages, etc.
    *   **Loading Bar/Spinner Elements:** For the initial game load.
    *   **Win Display Backgrounds/Frames:** (Optional) Decorative elements for win amount displays.

## V. Particle Effects & Special Effects Assets

*   **Format:** Individual PNGs or spritesheets.
*   **Examples:**
    *   Win celebration particles (e.g., coins, stars, thematic glints).
    *   Symbol landing dust/impact puffs.
    *   Trail effects for animated paylines.
    *   Special symbol activation glows or flares.
*   **Considerations:** Keep particle counts and complexity in check for performance, especially on mobile.

## VI. Sound Assets

*   **General:**
    *   High quality, clear audio.
    *   Balance volume levels across all sounds.
*   **Background Music (BGM):**
    *   Format: MP3.
    *   Loopable seamlessly.
    *   Main game BGM and potentially a different BGM for bonus rounds.
*   **Sound Effects (SFX):**
    *   Format: WAV for short effects, MP3 for longer ones if necessary.
    *   **Reel SFX:**
        *   Reel spin start.
        *   Individual reel stop (can have slight variations).
        *   Anticipation sound for special symbols.
    *   **Symbol SFX:**
        *   Symbol landing.
        *   Win jingles (small, medium, big wins).
        *   Scatter/Bonus symbol trigger sounds.
    *   **UI SFX:**
        *   Button clicks (generic and/or specific).
        *   Bet change sound.
    *   **Win Presentation SFX:**
        *   Payline appearing/highlighting.
        *   Win amount counting up.
        *   "Big Win," "Mega Win" stinger sounds.
        *   **Note:** The `gameConfig.json` can specify keys for `big_win_sfx` and `mega_win_sfx` within the `win_presentation` object, allowing for theme-specific big win sounds (e.g., `"big_win_sfx": "theme_sfx_big_win"`).

## VII. Configuration File (`gameConfig.json`)

While not an "asset" in the traditional sense, the `gameConfig.json` file is crucial for defining how assets are used. It will reference all asset file paths and include parameters for:
*   Symbol definitions, including paths to images and animation data (e.g., `animations.win` object).
*   Layout (rows, columns).
*   Animation timings and easing functions (e.g., `reels_config` object for reel animations).
*   Payline definitions.
*   UI element configurations.
*   Sound event triggers (e.g., `win_presentation.big_win_sfx`).
*   Big Win thresholds and animation settings (e.g., `win_presentation` object).

Ensure all asset file paths in `gameConfig.json` accurately reflect the directory structure for the specific slot theme.
---
# Developer Documentation Update Outline

The following sections and information should be added to or updated in the project's developer documentation to reflect the new slot system features:

## 1. New Phaser Scenes (`ModernSlotScene.js`, `ModernUIScene.js`)

*   **Introduction:**
    *   Brief overview of `ModernSlotScene.js` as the primary gameplay scene and `ModernUIScene.js` as the primary UI scene for new slot games.
    *   Highlight key features:
        *   Responsive grid layout in `ModernSlotScene.js`.
        *   Enhanced symbol landing and reel stop animations.
        *   "Big Win" / "Mega Win" presentation sequences.
        *   Configurable symbol win animations (pulse, shake).
*   **Scene Launching:**
    *   Explain that `PreloadScene.js` is now configured to launch `ModernSlotScene` and `ModernUIScene` by default for new slots.
*   **Key Responsibilities:**
    *   `ModernSlotScene.js`: Manages game logic, reel mechanics, win evaluation, core visual effects (reels, symbols, big win text).
    *   `ModernUIScene.js`: Manages UI elements (spin button, bet controls, balance display, win display), and relays user input to the game logic.

## 2. `gameConfig.json` Enhancements

*   **Overview:** Explain that `gameConfig.json` has new sections to control the enhanced features.
*   **Detailed Configuration Sections:**
    *   **`symbols[n].animations.win`:**
        *   Location: Within each symbol object in the `game.symbols` array.
        *   Purpose: Defines the standard win animation for that symbol.
        *   Structure: `{"type": "animation_type", ...parameters}`
        *   Supported `type` values:
            *   `"pulse"`: Parameters: `scale` (e.g., 1.25), `duration` (e.g., 300ms).
            *   `"shake"`: Parameters: `strength` (pixel offset, e.g., 5), `duration` (e.g., 400ms for the entire shake sequence).
        *   Example: `{"id": 1, "name": "Cherry", ..., "animations": {"win": {"type": "pulse", "scale": 1.2, "duration": 250}}}`
    *   **`game.reels_config`:**
        *   Location: Directly under the `game` object.
        *   Purpose: Controls global reel animation parameters.
        *   Structure & Parameters:
            *   `stop_ease_function` (string, e.g., "Back.easeOut"): Phaser easing function for reel container stop.
            *   `stop_ease_params` (array, e.g., `[1.5]`): Parameters for the stop ease function.
            *   `symbol_settle_ease_function` (string, e.g., "Bounce.easeOut"): Phaser easing function for individual symbol settle.
            *   `symbol_settle_duration` (number, e.g., 250): Duration in ms for symbol settle animation.
    *   **`game.win_presentation`:**
        *   Location: Directly under the `game` object.
        *   Purpose: Configures thresholds and assets for Big/Mega win presentations.
        *   Structure & Parameters:
            *   `big_win_threshold_multiplier` (number, e.g., 20): Bet multiplier to trigger "Big Win".
            *   `mega_win_threshold_multiplier` (number, e.g., 50): Bet multiplier to trigger "Mega Win".
            *   `big_win_sfx` (string, e.g., "theme_sfx_big_win"): Sound key for Big Win.
            *   `mega_win_sfx` (string, e.g., "theme_sfx_mega_win"): Sound key for Mega Win.
    *   **`game.holdAndWinBonus` (If documenting as standard):**
        *   Location: Directly under the `game` object.
        *   Purpose: Configures a Hold and Win style bonus game.
        *   Key Parameters: `triggerSymbolId`, `minTriggerCount`, `coinSymbolId`, `defaultCoinValue`, `reSpinsAwarded`, `bonusBackgroundAsset`, `bonusMusic`. (Refer to `slotfactory.py` or `casino_be/utils/slot_builder.py` for full structure if needed).
*   **Configuring Grid Layouts:**
    *   Explain that `game.layout.rows` and `game.layout.columns` define the grid dimensions.
    *   `game.reel_strips` must be an array of arrays, with the outer array length matching `columns`, and each inner array (strip) containing symbol IDs. Strip length should be significantly greater than `rows` (e.g., 20-50 symbols).
    *   `game.paylines` is an array of payline definitions. Each payline is an array of `[col, row]` coordinate pairs (0-indexed). Provide examples for different grid sizes if possible, or link to a tool/helper for generating them.
    *   Mention that for very large grids (e.g., 6x6+), "ways to win" or "cluster pays" might be more suitable than traditional paylines, but these are not yet fully implemented in `ModernSlotScene.js`'s payline evaluation.

## 3. Asset Pipeline

*   **Reference `ASSET_SPECIFICATIONS.md`:** State that `ASSET_SPECIFICATIONS.md` (located in `casino_fe/`) is the primary document for detailed asset requirements (formats, resolutions, naming, content guidelines).
*   Briefly reiterate key points: PNGs for images, MP3/WAV for audio, @1x and @2x scales.

## 4. Customizing Slot Themes

*   **Using `slotfactory.py` (GenAI):**
    *   Explain that `slotfactory.py` now uses an updated prompt to generate `gameConfig.json` files that include the new fields (`animations.win`, `reels_config`, `win_presentation`, optional `holdAndWinBonus`).
    *   The image generation prompts in `slotfactory.py` have also been updated to align with `ASSET_SPECIFICATIONS.md` for better quality and consistency.
    *   Mention that developers should review and potentially fine-tune the AI-generated `gameConfig.json` and assets.
*   **Using `casino_be/utils/slot_builder.py` (Placeholder):**
    *   Explain that this script also generates a `gameConfig.json` with the new fields, providing default values suitable for testing and further customization.
    *   This script generates placeholder text files for assets, which need to be replaced with actual themed graphics and sounds.

## 5. Event Bus Communication

*   **Key New Events for Integration:**
    *   `bigWinStarted`: Emitted by `ModernSlotScene` when the Big Win sequence begins. UI scenes might listen to this to hide conflicting elements.
    *   `bigWinEnded`: Emitted by `ModernSlotScene` when the Big Win sequence (including count-up and any final line displays) fully completes.
    *   `bonusWinningsCalculated`: Emitted by `ModernSlotScene` after a bonus round to inform Vue/UI of the total bonus win amount.
    *   `phaserSpinResult`: (Replaces `spinAnimationComplete`) Emitted by `ModernSlotScene` to `Slot.vue` with the final spin outcome.
*   Briefly explain the primary direction: Vue (`Slot.vue`) -> Phaser Scenes (`ModernSlotScene`, `ModernUIScene`) for commands like spin; Phaser Scenes -> Vue for results, errors, and UI updates.
---
