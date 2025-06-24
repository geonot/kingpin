import random
import copy # For deep copies if needed for complex state manipulation
import json # Added for parsing sphere_colors/textures if stored as JSON string

# --- Helper Functions ---

def _generate_sphere_grid(dimensions: dict, colors: list, textures: list) -> list:
    """
    Generates a grid of spheres with random colors and textures.
    dimensions: {"width": int, "height": int}
    colors: List of available color strings (e.g., ["#FF0000", "#00FF00"])
    textures: List of available texture strings (e.g., ["smooth", "glossy"])
    """
    if not dimensions or 'width' not in dimensions or 'height' not in dimensions:
        raise ValueError("Invalid dimensions for sphere grid.")
    if not colors:
        # Fallback if colors list is empty, though slot config should provide valid ones.
        colors = ["#FFFFFF"] # Default to white if no colors provided
        # raise ValueError("No sphere colors defined.")
    if not textures: # Default texture if not specified
        textures = ["default"]

    grid = []
    for _ in range(dimensions['height']):
        row = []
        for _ in range(dimensions['width']):
            sphere = {
                "color": random.choice(colors),
                "texture": random.choice(textures)
                # Add other properties like "is_prism": False initially
            }
            row.append(sphere)
        grid.append(row)
    return grid

def _check_cluster_wins(grid: list, winning_patterns: dict, base_bet: int) -> tuple[int, list]:
    """
    Checks for cluster wins.
    This is a simplified example. A full implementation would need a robust
    algorithm to find connected components (clusters) of same-colored spheres.

    winning_patterns: {
        "clusters": { "min_size": 3, "pay_multipliers": { "3": 1, "4": 2, ... } }
    }
    Returns (total_win_for_clusters, list_of_cluster_events)
    """
    if not grid or not winning_patterns or "clusters" not in winning_patterns:
        return 0, []

    cluster_config = winning_patterns["clusters"]
    min_size = cluster_config.get("min_size", 3)
    pay_multipliers = cluster_config.get("pay_multipliers", {})

    height = len(grid)
    width = len(grid[0]) if height > 0 else 0
    visited = [[False for _ in range(width)] for _ in range(height)] # To avoid re-processing spheres in found clusters
    total_win = 0
    win_events = []

    for r in range(height):
        for c in range(width):
            if visited[r][c]:
                continue

            sphere_color = grid[r][c]["color"]

            # Placeholder: Simplified horizontal cluster detection
            # A real implementation needs a graph traversal (DFS/BFS) to find actual clusters.
            count_horizontal = 0
            temp_nodes = []
            for i in range(c, width): # Check right from current sphere
                if not visited[r][i] and grid[r][i]["color"] == sphere_color:
                    count_horizontal += 1
                    temp_nodes.append((r,i))
                else:
                    break # End of this potential horizontal line

            if count_horizontal >= min_size:
                current_cluster_size = count_horizontal
                # Mark these nodes as visited for this specific horizontal check
                # Note: This simplistic visited marking is only for this horizontal check.
                # A real DFS/BFS would handle visited nodes more comprehensively.
                for sr, sc in temp_nodes:
                    visited[sr][sc] = True

                payout_multiplier_key = str(current_cluster_size)
                # Handle "X+" style keys (e.g., "7+")
                if payout_multiplier_key not in pay_multipliers:
                    plus_keys = sorted(
                        [int(k.replace('+', '')) for k in pay_multipliers.keys() if '+' in k],
                        reverse=True
                    )
                    found_key_to_use = None
                    for pk_val in plus_keys:
                        if current_cluster_size >= pk_val:
                            found_key_to_use = str(pk_val) + '+'
                            break
                    if found_key_to_use:
                        payout_multiplier_key = found_key_to_use
                    else: # Fallback to largest exact number match if no "X+" matches
                        exact_numeric_keys = sorted(
                            [int(k) for k in pay_multipliers.keys() if k.isdigit()],
                            reverse=True
                        )
                        if exact_numeric_keys:
                             if current_cluster_size > exact_numeric_keys[0]:
                                 payout_multiplier_key = str(exact_numeric_keys[0])
                             # else, key remains as current_cluster_size, may result in 0 multiplier if not defined

                multiplier = pay_multipliers.get(payout_multiplier_key, 0.0)
                if isinstance(multiplier, (int, float)) and multiplier > 0:
                    win = int(base_bet * float(multiplier))
                    total_win += win
                    win_events.append(f"cluster_of_{current_cluster_size}_{sphere_color.lower().replace('#','')}")

    return total_win, win_events


# --- Main Handler ---

def handle_symphony_spheres_pulse(user, slot_config, game_session, bet_amount_sats: int):
    """
    Handles the core game logic for a "Symphony of Spheres" pulse (spin).
    """
    # --- Configuration Extraction ---
    raw_sphere_colors = slot_config.sphere_colors
    sphere_colors = []
    if isinstance(raw_sphere_colors, str):
        try: sphere_colors = json.loads(raw_sphere_colors)
        except json.JSONDecodeError: pass
    elif isinstance(raw_sphere_colors, list):
        sphere_colors = raw_sphere_colors
    if not sphere_colors: sphere_colors = ["#C0C0C0"] # Default to silver if parsing fails or empty

    raw_sphere_textures = slot_config.sphere_textures
    sphere_textures = []
    if isinstance(raw_sphere_textures, str):
        try: sphere_textures = json.loads(raw_sphere_textures)
        except json.JSONDecodeError: pass
    elif isinstance(raw_sphere_textures, list):
        sphere_textures = raw_sphere_textures
    if not sphere_textures: sphere_textures = ["default_texture"]

    winning_patterns = slot_config.winning_patterns if isinstance(slot_config.winning_patterns, dict) else {}
    prism_config = slot_config.prism_sphere_config if isinstance(slot_config.prism_sphere_config, dict) else {}
    dimensions = slot_config.base_field_dimensions if isinstance(slot_config.base_field_dimensions, dict) else {"width": 8, "height": 8}


    # --- RNG for Sphere Generation ---
    final_spheres = _generate_sphere_grid(dimensions, sphere_colors, sphere_textures)

    prism_active_this_pulse = False
    if prism_config.get("acts_as_wild") and random.random() < prism_config.get("appearance_rate", 0.0):
        prism_active_this_pulse = True

    # --- Winning Pattern Logic ---
    win_amount_sats = 0
    winning_events = []
    is_cascade_active = False

    # Using bet_amount_sats as base for pattern multipliers
    cluster_win_sats, cluster_events = _check_cluster_wins(final_spheres, winning_patterns, bet_amount_sats)
    if cluster_win_sats > 0:
        win_amount_sats += cluster_win_sats
        winning_events.extend(cluster_events)
        is_cascade_active = True

    if prism_active_this_pulse and win_amount_sats > 0:
        prism_multiplier = prism_config.get("multiplier_value", 1.0)
        if isinstance(prism_multiplier, (int, float)) and prism_multiplier > 1.0:
            win_amount_sats = int(win_amount_sats * prism_multiplier)
            winning_events.append(f"prism_multiplier_x{prism_multiplier}")

    # --- "Harmony" Event (Jackpot - Placeholder) ---
    harmony_event_triggered = False
    # Example: if a very specific large cluster of a rare color formed.
    # if _check_harmony_event(final_spheres, winning_patterns.get("harmony")):
    #    harmony_win_sats = winning_patterns.get("harmony", {}).get("jackpot_amount", 1000 * bet_amount_sats)
    #    win_amount_sats += harmony_win_sats
    #    winning_events.append("HARMONY_JACKPOT")
    #    harmony_event_triggered = True
    #    is_cascade_active = True

    return {
        "final_spheres": final_spheres,
        "win_amount_sats": win_amount_sats,
        "winning_events": winning_events,
        "harmony_event_triggered": harmony_event_triggered,
        "is_cascade_active": is_cascade_active,
    }
