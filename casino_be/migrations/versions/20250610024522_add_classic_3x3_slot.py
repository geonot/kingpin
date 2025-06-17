"""Add Classic 3x3 slot machine

Revision ID: classic_3x3_slot
Revises: fix_slot_configs
Create Date: 2025-06-10 02:45:22

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers
revision = 'classic_3x3_slot'
down_revision = 'fix_slot_configs'
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    
    # Check if classic3x3 slot already exists
    existing = connection.execute(sa.text("SELECT id FROM slot WHERE short_name = 'classic3x3'")).fetchone()
    if existing:
        print("Classic 3x3 slot already exists, skipping...")
        return
    
    # Insert the Classic 3x3 slot using correct table and column names
    slot_result = connection.execute(sa.text("""
        INSERT INTO slot (name, short_name, description, num_rows, num_columns, num_symbols, 
                         wild_symbol_id, scatter_symbol_id, bonus_type, bonus_subtype, 
                         bonus_multiplier, bonus_spins_trigger_count, bonus_spins_awarded, 
                         asset_directory, rtp, volatility, is_active, is_multiway, 
                         is_cascading, cascade_type, min_symbols_to_match, win_multipliers, 
                         created_at)
        VALUES ('Classic 3x3', 'classic3x3', 'A traditional 3x3 classic slot machine with fruits and lucky sevens', 
                3, 3, 7, 7, 6, 'free_spins', 'classic', 2.0, 3, 10, '/classic3x3/', 
                96.5, 'Medium', true, false, false, null, null, '[]', :now)
        RETURNING id
    """), {"now": datetime.utcnow()})
    
    slot_id = slot_result.fetchone()[0]
    
    # Insert symbols using correct table and column names
    symbols = [
        (1, "cherry", "/classic3x3/cherry.png", 1.0, '{"value_multipliers": {"3": 5}}'),
        (2, "lemon", "/classic3x3/lemon.png", 2.0, '{"value_multipliers": {"3": 10}}'),
        (3, "orange", "/classic3x3/orange.png", 3.0, '{"value_multipliers": {"3": 15}}'),
        (4, "plum", "/classic3x3/plum.png", 4.0, '{"value_multipliers": {"3": 20}}'),
        (5, "bar", "/classic3x3/bar.png", 10.0, '{"value_multipliers": {"3": 50}}'),
        (6, "bell", "/classic3x3/bell.png", 0.0, '{"scatter_payouts": {"3": 10}}'),
        (7, "seven", "/classic3x3/seven.png", 50.0, '{"value_multipliers": {"3": 250}}')
    ]
    
    for symbol_id, name, icon, value_mult, json_data in symbols:
        connection.execute(sa.text("""
            INSERT INTO slot_symbol (slot_id, symbol_internal_id, name, img_link, value_multiplier, data)
            VALUES (:slot_id, :symbol_id, :name, :icon, :value_mult, CAST(:data AS jsonb))
        """), {
            "slot_id": slot_id,
            "symbol_id": symbol_id,
            "name": name,
            "icon": icon,
            "value_mult": value_mult,
            "data": json_data
        })
    
    # Update the slot with reel configuration
    reel_config_json = '''
    {
        "paylines": [
            {"id": 0, "coords": [[0,0], [0,1], [0,2]]},
            {"id": 1, "coords": [[1,0], [1,1], [1,2]]},
            {"id": 2, "coords": [[2,0], [2,1], [2,2]]},
            {"id": 3, "coords": [[0,0], [1,1], [2,2]]},
            {"id": 4, "coords": [[2,0], [1,1], [0,2]]}
        ],
        "reel_strips": [
            [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 1, 2, 3, 1, 4, 5, 1, 2, 3, 4, 5, 6, 7],
            [2, 1, 4, 3, 5, 6, 1, 7, 2, 3, 4, 1, 5, 2, 3, 1, 4, 6, 1, 2, 3, 4, 5, 1, 2],
            [3, 2, 1, 4, 5, 1, 6, 2, 7, 3, 4, 5, 1, 2, 3, 4, 1, 5, 6, 1, 2, 3, 4, 1, 5]
        ]
    }
    '''
    
    connection.execute(sa.text("""
        UPDATE slot SET reel_configurations = :config::jsonb WHERE id = :slot_id
    """), {"config": reel_config_json, "slot_id": slot_id})
    
    print(f"Classic 3x3 slot added successfully with ID: {slot_id}")

def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM slot_symbol WHERE slot_id IN (SELECT id FROM slot WHERE short_name = 'classic3x3')"))
    connection.execute(sa.text("DELETE FROM slot WHERE short_name = 'classic3x3'"))