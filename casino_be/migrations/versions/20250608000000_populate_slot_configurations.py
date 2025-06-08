"""Populate slot configurations from gameConfig files

Revision ID: populate_slots
Revises: consolidated_models
Create Date: 2025-06-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import Integer, String, Float, Boolean, BigInteger, JSON, Text, DateTime
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = 'populate_slots'
down_revision = 'consolidated_models'
branch_labels = None
depends_on = None

def upgrade():
    # Define table structures for data insertion
    slot_table = table('slot',
        column('id', Integer),
        column('name', String),
        column('description', Text),
        column('num_rows', Integer),
        column('num_columns', Integer),
        column('num_symbols', Integer),
        column('wild_symbol_id', Integer),
        column('scatter_symbol_id', Integer),
        column('bonus_type', String),
        column('bonus_subtype', String),
        column('bonus_multiplier', Float),
        column('bonus_spins_trigger_count', Integer),
        column('bonus_spins_awarded', Integer),
        column('short_name', String),
        column('asset_directory', String),
        column('rtp', Float),
        column('volatility', String),
        column('is_active', Boolean),
        column('is_multiway', Boolean),
        column('reel_configurations', JSON),
        column('is_cascading', Boolean),
        column('cascade_type', String),
        column('min_symbols_to_match', Integer),
        column('win_multipliers', JSON),
        column('created_at', DateTime)
    )
    
    slot_symbol_table = table('slot_symbol',
        column('id', Integer),
        column('slot_id', Integer),
        column('symbol_internal_id', Integer),
        column('name', String),
        column('img_link', String),
        column('value_multiplier', Float),
        column('data', JSON)
    )
    
    slot_bet_table = table('slot_bet',
        column('id', Integer),
        column('slot_id', Integer),
        column('bet_amount', BigInteger)
    )

    # Insert Slot 1 - Hack the Planet
    op.bulk_insert(slot_table, [
        {
            'id': 1,
            'name': 'Hack the Planet',
            'description': 'A cyberpunk-themed slot machine with hacking elements',
            'num_rows': 3,
            'num_columns': 5,
            'num_symbols': 9,
            'wild_symbol_id': 9,
            'scatter_symbol_id': 8,
            'bonus_type': 'free_spins',
            'bonus_subtype': 'scatter_trigger',
            'bonus_multiplier': 3.0,
            'bonus_spins_trigger_count': 3,
            'bonus_spins_awarded': 10,
            'short_name': 'hack',
            'asset_directory': '/slot1/',
            'rtp': 96.5,
            'volatility': 'medium',
            'is_active': True,
            'is_multiway': False,
            'reel_configurations': {
                'paylines': [
                    {'id': 0, 'coords': [[0,0],[0,1],[0,2],[0,3],[0,4]]},
                    {'id': 1, 'coords': [[1,0],[1,1],[1,2],[1,3],[1,4]]},
                    {'id': 2, 'coords': [[2,0],[2,1],[2,2],[2,3],[2,4]]},
                    {'id': 3, 'coords': [[0,0],[1,1],[2,2],[1,3],[0,4]]},
                    {'id': 4, 'coords': [[2,0],[1,1],[0,2],[1,3],[2,4]]},
                    {'id': 5, 'coords': [[0,0],[0,1],[1,2],[2,3],[2,4]]},
                    {'id': 6, 'coords': [[2,0],[2,1],[1,2],[0,3],[0,4]]},
                    {'id': 7, 'coords': [[1,0],[0,1],[0,2],[0,3],[1,4]]},
                    {'id': 8, 'coords': [[1,0],[2,1],[2,2],[2,3],[1,4]]},
                    {'id': 9, 'coords': [[0,0],[1,1],[0,2],[1,3],[0,4]]}
                ],
                'payouts': [
                    {'symbol_id': 1, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 1, 'matches': 4, 'multiplier': 1}, {'symbol_id': 1, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 2, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 2, 'matches': 4, 'multiplier': 1}, {'symbol_id': 2, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 3, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 3, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 3, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 4, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 4, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 4, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 5, 'matches': 3, 'multiplier': 1}, {'symbol_id': 5, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 5, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 6, 'matches': 3, 'multiplier': 1}, {'symbol_id': 6, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 6, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 7, 'matches': 3, 'multiplier': 1.5}, {'symbol_id': 7, 'matches': 4, 'multiplier': 5}, {'symbol_id': 7, 'matches': 5, 'multiplier': 10},
                    {'symbol_id': 8, 'matches': 3, 'multiplier': 2}, {'symbol_id': 8, 'matches': 4, 'multiplier': 10}, {'symbol_id': 8, 'matches': 5, 'multiplier': 50}
                ]
            },
            'is_cascading': False,
            'cascade_type': None,
            'min_symbols_to_match': 3,
            'win_multipliers': None,
            'created_at': datetime.now(timezone.utc)
        }
    ])

    # Insert Slot 1 Symbols
    slot1_symbols = [
        {'slot_id': 1, 'symbol_internal_id': 1, 'name': 'Symbol 1', 'img_link': '/slot1/sprite_0.png', 'value_multiplier': 1.5},
        {'slot_id': 1, 'symbol_internal_id': 2, 'name': 'Symbol 2', 'img_link': '/slot1/sprite_1.png', 'value_multiplier': 2},
        {'slot_id': 1, 'symbol_internal_id': 3, 'name': 'Symbol 3', 'img_link': '/slot1/sprite_2.png', 'value_multiplier': 2.5},
        {'slot_id': 1, 'symbol_internal_id': 4, 'name': 'Symbol 4', 'img_link': '/slot1/sprite_3.png', 'value_multiplier': 3},
        {'slot_id': 1, 'symbol_internal_id': 5, 'name': 'Symbol 5', 'img_link': '/slot1/sprite_4.png', 'value_multiplier': 5},
        {'slot_id': 1, 'symbol_internal_id': 6, 'name': 'Symbol 6', 'img_link': '/slot1/sprite_5.png', 'value_multiplier': 10},
        {'slot_id': 1, 'symbol_internal_id': 7, 'name': 'Symbol 7', 'img_link': '/slot1/sprite_6.png', 'value_multiplier': 20},
        {'slot_id': 1, 'symbol_internal_id': 8, 'name': 'Scatter', 'img_link': '/slot1/sprite_7.png', 'value_multiplier': 0},
        {'slot_id': 1, 'symbol_internal_id': 9, 'name': 'Wild', 'img_link': '/slot1/sprite_8.png', 'value_multiplier': 0}
    ]
    
    op.bulk_insert(slot_symbol_table, slot1_symbols)

    # Insert Slot 1 Bet Options (converting from base units to satoshis)
    slot1_bets = [
        {'slot_id': 1, 'bet_amount': 10},
        {'slot_id': 1, 'bet_amount': 20},
        {'slot_id': 1, 'bet_amount': 50},
        {'slot_id': 1, 'bet_amount': 100},
        {'slot_id': 1, 'bet_amount': 200},
        {'slot_id': 1, 'bet_amount': 500}
    ]
    
    op.bulk_insert(slot_bet_table, slot1_bets)

    # Insert Slot 2 - Dragon Legend
    op.bulk_insert(slot_table, [
        {
            'id': 2,
            'name': 'Dragon Legend',
            'description': 'A mystical dragon-themed slot with ancient treasures',
            'num_rows': 3,
            'num_columns': 5,
            'num_symbols': 14,
            'wild_symbol_id': 14,
            'scatter_symbol_id': 13,
            'bonus_type': 'free_spins',
            'bonus_subtype': 'scatter_trigger',
            'bonus_multiplier': 2.0,
            'bonus_spins_trigger_count': 3,
            'bonus_spins_awarded': 10,
            'short_name': 'dragon',
            'asset_directory': '/slot2/',
            'rtp': 96.8,
            'volatility': 'high',
            'is_active': True,
            'is_multiway': False,
            'reel_configurations': {
                'paylines': [
                    {'id': 0, 'coords': [[0,0],[0,1],[0,2],[0,3],[0,4]]},
                    {'id': 1, 'coords': [[1,0],[1,1],[1,2],[1,3],[1,4]]},
                    {'id': 2, 'coords': [[2,0],[2,1],[2,2],[2,3],[2,4]]},
                    {'id': 3, 'coords': [[0,0],[1,1],[2,2],[1,3],[0,4]]},
                    {'id': 4, 'coords': [[2,0],[1,1],[0,2],[1,3],[2,4]]},
                    {'id': 5, 'coords': [[0,0],[0,1],[1,2],[2,3],[2,4]]},
                    {'id': 6, 'coords': [[2,0],[2,1],[1,2],[0,3],[0,4]]},
                    {'id': 7, 'coords': [[1,0],[0,1],[0,2],[0,3],[1,4]]},
                    {'id': 8, 'coords': [[1,0],[2,1],[2,2],[2,3],[1,4]]},
                    {'id': 9, 'coords': [[0,0],[1,1],[0,2],[1,3],[0,4]]}
                ],
                'payouts': [
                    {'symbol_id': 1, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 1, 'matches': 4, 'multiplier': 1}, {'symbol_id': 1, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 2, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 2, 'matches': 4, 'multiplier': 1}, {'symbol_id': 2, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 3, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 3, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 3, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 4, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 4, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 4, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 5, 'matches': 3, 'multiplier': 1}, {'symbol_id': 5, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 5, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 6, 'matches': 3, 'multiplier': 1}, {'symbol_id': 6, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 6, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 7, 'matches': 3, 'multiplier': 1.5}, {'symbol_id': 7, 'matches': 4, 'multiplier': 5}, {'symbol_id': 7, 'matches': 5, 'multiplier': 10},
                    {'symbol_id': 8, 'matches': 3, 'multiplier': 1.5}, {'symbol_id': 8, 'matches': 4, 'multiplier': 5}, {'symbol_id': 8, 'matches': 5, 'multiplier': 10},
                    {'symbol_id': 9, 'matches': 3, 'multiplier': 2}, {'symbol_id': 9, 'matches': 4, 'multiplier': 7.5}, {'symbol_id': 9, 'matches': 5, 'multiplier': 15},
                    {'symbol_id': 10, 'matches': 3, 'multiplier': 2}, {'symbol_id': 10, 'matches': 4, 'multiplier': 7.5}, {'symbol_id': 10, 'matches': 5, 'multiplier': 15},
                    {'symbol_id': 11, 'matches': 3, 'multiplier': 2.5}, {'symbol_id': 11, 'matches': 4, 'multiplier': 10}, {'symbol_id': 11, 'matches': 5, 'multiplier': 25},
                    {'symbol_id': 12, 'matches': 3, 'multiplier': 2.5}, {'symbol_id': 12, 'matches': 4, 'multiplier': 10}, {'symbol_id': 12, 'matches': 5, 'multiplier': 25},
                    {'symbol_id': 13, 'matches': 3, 'multiplier': 2}, {'symbol_id': 13, 'matches': 4, 'multiplier': 10}, {'symbol_id': 13, 'matches': 5, 'multiplier': 50}
                ]
            },
            'is_cascading': False,
            'cascade_type': None,
            'min_symbols_to_match': 3,
            'win_multipliers': None,
            'created_at': datetime.now(timezone.utc)
        }
    ])

    # Insert Slot 2 Symbols
    slot2_symbols = [
        {'slot_id': 2, 'symbol_internal_id': 1, 'name': 'Symbol 1', 'img_link': '/slot2/sprite_0.png', 'value_multiplier': 1.5},
        {'slot_id': 2, 'symbol_internal_id': 2, 'name': 'Symbol 2', 'img_link': '/slot2/sprite_1.png', 'value_multiplier': 2},
        {'slot_id': 2, 'symbol_internal_id': 3, 'name': 'Symbol 3', 'img_link': '/slot2/sprite_2.png', 'value_multiplier': 2.5},
        {'slot_id': 2, 'symbol_internal_id': 4, 'name': 'Symbol 4', 'img_link': '/slot2/sprite_3.png', 'value_multiplier': 3},
        {'slot_id': 2, 'symbol_internal_id': 5, 'name': 'Symbol 5', 'img_link': '/slot2/sprite_4.png', 'value_multiplier': 5},
        {'slot_id': 2, 'symbol_internal_id': 6, 'name': 'Symbol 6', 'img_link': '/slot2/sprite_5.png', 'value_multiplier': 10},
        {'slot_id': 2, 'symbol_internal_id': 7, 'name': 'Symbol 7', 'img_link': '/slot2/sprite_6.png', 'value_multiplier': 20},
        {'slot_id': 2, 'symbol_internal_id': 8, 'name': 'Symbol 8', 'img_link': '/slot2/sprite_7.png', 'value_multiplier': 30},
        {'slot_id': 2, 'symbol_internal_id': 9, 'name': 'Symbol 9', 'img_link': '/slot2/sprite_8.png', 'value_multiplier': 40},
        {'slot_id': 2, 'symbol_internal_id': 10, 'name': 'Symbol 10', 'img_link': '/slot2/sprite_9.png', 'value_multiplier': 50},
        {'slot_id': 2, 'symbol_internal_id': 11, 'name': 'Symbol 11', 'img_link': '/slot2/sprite_10.png', 'value_multiplier': 75},
        {'slot_id': 2, 'symbol_internal_id': 12, 'name': 'Symbol 12', 'img_link': '/slot2/sprite_11.png', 'value_multiplier': 100},
        {'slot_id': 2, 'symbol_internal_id': 13, 'name': 'Scatter', 'img_link': '/slot2/sprite_12.png', 'value_multiplier': 0},
        {'slot_id': 2, 'symbol_internal_id': 14, 'name': 'Wild', 'img_link': '/slot2/sprite_13.png', 'value_multiplier': 0}
    ]
    
    op.bulk_insert(slot_symbol_table, slot2_symbols)

    # Insert Slot 2 Bet Options
    slot2_bets = [
        {'slot_id': 2, 'bet_amount': 10},
        {'slot_id': 2, 'bet_amount': 20},
        {'slot_id': 2, 'bet_amount': 50},
        {'slot_id': 2, 'bet_amount': 100},
        {'slot_id': 2, 'bet_amount': 200},
        {'slot_id': 2, 'bet_amount': 500}
    ]
    
    op.bulk_insert(slot_bet_table, slot2_bets)

    # Insert Slot 3 - Synthwave Future
    op.bulk_insert(slot_table, [
        {
            'id': 3,
            'name': 'Synthwave Future',
            'description': 'A retro-futuristic synthwave themed slot machine',
            'num_rows': 3,
            'num_columns': 5,
            'num_symbols': 14,
            'wild_symbol_id': 12,
            'scatter_symbol_id': 13,
            'bonus_type': 'free_spins',
            'bonus_subtype': 'scatter_trigger',
            'bonus_multiplier': 2.0,
            'bonus_spins_trigger_count': 3,
            'bonus_spins_awarded': 8,
            'short_name': 'synthwave',
            'asset_directory': '/slot3/',
            'rtp': 96.2,
            'volatility': 'medium',
            'is_active': True,
            'is_multiway': False,
            'reel_configurations': {
                'paylines': [
                    {'id': 0, 'coords': [[0,0],[0,1],[0,2],[0,3],[0,4]]},
                    {'id': 1, 'coords': [[1,0],[1,1],[1,2],[1,3],[1,4]]},
                    {'id': 2, 'coords': [[2,0],[2,1],[2,2],[2,3],[2,4]]},
                    {'id': 3, 'coords': [[0,0],[1,1],[2,2],[1,3],[0,4]]},
                    {'id': 4, 'coords': [[2,0],[1,1],[0,2],[1,3],[2,4]]},
                    {'id': 5, 'coords': [[0,0],[0,1],[1,2],[2,3],[2,4]]},
                    {'id': 6, 'coords': [[2,0],[2,1],[1,2],[0,3],[0,4]]},
                    {'id': 7, 'coords': [[1,0],[0,1],[0,2],[0,3],[1,4]]},
                    {'id': 8, 'coords': [[1,0],[2,1],[2,2],[2,3],[1,4]]},
                    {'id': 9, 'coords': [[0,0],[1,1],[0,2],[1,3],[0,4]]}
                ],
                'payouts': [
                    {'symbol_id': 1, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 1, 'matches': 4, 'multiplier': 1}, {'symbol_id': 1, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 2, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 2, 'matches': 4, 'multiplier': 1}, {'symbol_id': 2, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 3, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 3, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 3, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 4, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 4, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 4, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 5, 'matches': 3, 'multiplier': 1}, {'symbol_id': 5, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 5, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 6, 'matches': 3, 'multiplier': 1}, {'symbol_id': 6, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 6, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 7, 'matches': 3, 'multiplier': 1.5}, {'symbol_id': 7, 'matches': 4, 'multiplier': 5}, {'symbol_id': 7, 'matches': 5, 'multiplier': 10},
                    {'symbol_id': 8, 'matches': 3, 'multiplier': 1.5}, {'symbol_id': 8, 'matches': 4, 'multiplier': 5}, {'symbol_id': 8, 'matches': 5, 'multiplier': 10},
                    {'symbol_id': 9, 'matches': 3, 'multiplier': 2}, {'symbol_id': 9, 'matches': 4, 'multiplier': 7.5}, {'symbol_id': 9, 'matches': 5, 'multiplier': 15},
                    {'symbol_id': 10, 'matches': 3, 'multiplier': 2}, {'symbol_id': 10, 'matches': 4, 'multiplier': 7.5}, {'symbol_id': 10, 'matches': 5, 'multiplier': 15},
                    {'symbol_id': 11, 'matches': 3, 'multiplier': 2.5}, {'symbol_id': 11, 'matches': 4, 'multiplier': 10}, {'symbol_id': 11, 'matches': 5, 'multiplier': 25},
                    {'symbol_id': 14, 'matches': 3, 'multiplier': 2.5}, {'symbol_id': 14, 'matches': 4, 'multiplier': 10}, {'symbol_id': 14, 'matches': 5, 'multiplier': 25},
                    {'symbol_id': 13, 'matches': 3, 'multiplier': 2}, {'symbol_id': 13, 'matches': 4, 'multiplier': 10}, {'symbol_id': 13, 'matches': 5, 'multiplier': 50}
                ]
            },
            'is_cascading': False,
            'cascade_type': None,
            'min_symbols_to_match': 3,
            'win_multipliers': None,
            'created_at': datetime.now(timezone.utc)
        }
    ])

    # Insert Slot 3 Symbols
    slot3_symbols = [
        {'slot_id': 3, 'symbol_internal_id': 1, 'name': 'Symbol 1', 'img_link': '/slot3/sprite_0.png', 'value_multiplier': 1.5},
        {'slot_id': 3, 'symbol_internal_id': 2, 'name': 'Symbol 2', 'img_link': '/slot3/sprite_1.png', 'value_multiplier': 2},
        {'slot_id': 3, 'symbol_internal_id': 3, 'name': 'Symbol 3', 'img_link': '/slot3/sprite_2.png', 'value_multiplier': 2.5},
        {'slot_id': 3, 'symbol_internal_id': 4, 'name': 'Symbol 4', 'img_link': '/slot3/sprite_3.png', 'value_multiplier': 3},
        {'slot_id': 3, 'symbol_internal_id': 5, 'name': 'Symbol 5', 'img_link': '/slot3/sprite_4.png', 'value_multiplier': 5},
        {'slot_id': 3, 'symbol_internal_id': 6, 'name': 'Symbol 6', 'img_link': '/slot3/sprite_5.png', 'value_multiplier': 10},
        {'slot_id': 3, 'symbol_internal_id': 7, 'name': 'Symbol 7', 'img_link': '/slot3/sprite_6.png', 'value_multiplier': 20},
        {'slot_id': 3, 'symbol_internal_id': 8, 'name': 'Symbol 8', 'img_link': '/slot3/sprite_7.png', 'value_multiplier': 30},
        {'slot_id': 3, 'symbol_internal_id': 9, 'name': 'Symbol 9', 'img_link': '/slot3/sprite_8.png', 'value_multiplier': 40},
        {'slot_id': 3, 'symbol_internal_id': 10, 'name': 'Symbol 10', 'img_link': '/slot3/sprite_9.png', 'value_multiplier': 50},
        {'slot_id': 3, 'symbol_internal_id': 11, 'name': 'Symbol 11', 'img_link': '/slot3/sprite_10.png', 'value_multiplier': 75},
        {'slot_id': 3, 'symbol_internal_id': 12, 'name': 'Wild', 'img_link': '/slot3/sprite_11.png', 'value_multiplier': 0},
        {'slot_id': 3, 'symbol_internal_id': 13, 'name': 'Scatter', 'img_link': '/slot3/sprite_12.png', 'value_multiplier': 0},
        {'slot_id': 3, 'symbol_internal_id': 14, 'name': 'Symbol 14', 'img_link': '/slot3/sprite_13.png', 'value_multiplier': 100}
    ]
    
    op.bulk_insert(slot_symbol_table, slot3_symbols)

    # Insert Slot 3 Bet Options
    slot3_bets = [
        {'slot_id': 3, 'bet_amount': 10},
        {'slot_id': 3, 'bet_amount': 20},
        {'slot_id': 3, 'bet_amount': 50},
        {'slot_id': 3, 'bet_amount': 100},
        {'slot_id': 3, 'bet_amount': 200},
        {'slot_id': 3, 'bet_amount': 500}
    ]
    
    op.bulk_insert(slot_bet_table, slot3_bets)

    # Insert Slot 4 - Fruit and Cream
    op.bulk_insert(slot_table, [
        {
            'id': 4,
            'name': 'Fruit and Cream',
            'description': 'A classic fruit-themed slot machine with modern features',
            'num_rows': 3,
            'num_columns': 5,
            'num_symbols': 12,
            'wild_symbol_id': 12,
            'scatter_symbol_id': 11,
            'bonus_type': 'free_spins',
            'bonus_subtype': 'scatter_trigger',
            'bonus_multiplier': 2.0,
            'bonus_spins_trigger_count': 3,
            'bonus_spins_awarded': 8,
            'short_name': 'fruit',
            'asset_directory': '/slot4/',
            'rtp': 95.8,
            'volatility': 'low',
            'is_active': True,
            'is_multiway': False,
            'reel_configurations': {
                'paylines': [
                    {'id': 0, 'coords': [[0,0],[0,1],[0,2],[0,3],[0,4]]},
                    {'id': 1, 'coords': [[1,0],[1,1],[1,2],[1,3],[1,4]]},
                    {'id': 2, 'coords': [[2,0],[2,1],[2,2],[2,3],[2,4]]},
                    {'id': 3, 'coords': [[0,0],[1,1],[2,2],[1,3],[0,4]]},
                    {'id': 4, 'coords': [[2,0],[1,1],[0,2],[1,3],[2,4]]},
                    {'id': 5, 'coords': [[0,0],[0,1],[1,2],[2,3],[2,4]]},
                    {'id': 6, 'coords': [[2,0],[2,1],[1,2],[0,3],[0,4]]},
                    {'id': 7, 'coords': [[1,0],[0,1],[0,2],[0,3],[1,4]]},
                    {'id': 8, 'coords': [[1,0],[2,1],[2,2],[2,3],[1,4]]},
                    {'id': 9, 'coords': [[0,0],[1,1],[0,2],[1,3],[0,4]]}
                ],
                'payouts': [
                    {'symbol_id': 1, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 1, 'matches': 4, 'multiplier': 1}, {'symbol_id': 1, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 2, 'matches': 3, 'multiplier': 0.5}, {'symbol_id': 2, 'matches': 4, 'multiplier': 1}, {'symbol_id': 2, 'matches': 5, 'multiplier': 2},
                    {'symbol_id': 3, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 3, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 3, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 4, 'matches': 3, 'multiplier': 0.7}, {'symbol_id': 4, 'matches': 4, 'multiplier': 1.5}, {'symbol_id': 4, 'matches': 5, 'multiplier': 3},
                    {'symbol_id': 5, 'matches': 3, 'multiplier': 1}, {'symbol_id': 5, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 5, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 6, 'matches': 3, 'multiplier': 1}, {'symbol_id': 6, 'matches': 4, 'multiplier': 2.5}, {'symbol_id': 6, 'matches': 5, 'multiplier': 5},
                    {'symbol_id': 7, 'matches': 3, 'multiplier': 1.5}, {'symbol_id': 7, 'matches': 4, 'multiplier': 5}, {'symbol_id': 7, 'matches': 5, 'multiplier': 10},
                    {'symbol_id': 8, 'matches': 3, 'multiplier': 1.5}, {'symbol_id': 8, 'matches': 4, 'multiplier': 5}, {'symbol_id': 8, 'matches': 5, 'multiplier': 10},
                    {'symbol_id': 9, 'matches': 3, 'multiplier': 2}, {'symbol_id': 9, 'matches': 4, 'multiplier': 7.5}, {'symbol_id': 9, 'matches': 5, 'multiplier': 15},
                    {'symbol_id': 10, 'matches': 3, 'multiplier': 2}, {'symbol_id': 10, 'matches': 4, 'multiplier': 7.5}, {'symbol_id': 10, 'matches': 5, 'multiplier': 15},
                    {'symbol_id': 11, 'matches': 3, 'multiplier': 2}, {'symbol_id': 11, 'matches': 4, 'multiplier': 10}, {'symbol_id': 11, 'matches': 5, 'multiplier': 50}
                ]
            },
            'is_cascading': False,
            'cascade_type': None,
            'min_symbols_to_match': 3,
            'win_multipliers': None,
            'created_at': datetime.now(timezone.utc)
        }
    ])

    # Insert Slot 4 Symbols
    slot4_symbols = [
        {'slot_id': 4, 'symbol_internal_id': 1, 'name': 'Symbol 1', 'img_link': '/slot4/sprite_11.png', 'value_multiplier': 1.5},
        {'slot_id': 4, 'symbol_internal_id': 2, 'name': 'Symbol 2', 'img_link': '/slot4/sprite_1.png', 'value_multiplier': 2},
        {'slot_id': 4, 'symbol_internal_id': 3, 'name': 'Symbol 3', 'img_link': '/slot4/sprite_2.png', 'value_multiplier': 2.5},
        {'slot_id': 4, 'symbol_internal_id': 4, 'name': 'Symbol 4', 'img_link': '/slot4/sprite_3.png', 'value_multiplier': 3},
        {'slot_id': 4, 'symbol_internal_id': 5, 'name': 'Symbol 5', 'img_link': '/slot4/sprite_4.png', 'value_multiplier': 5},
        {'slot_id': 4, 'symbol_internal_id': 6, 'name': 'Symbol 6', 'img_link': '/slot4/sprite_5.png', 'value_multiplier': 10},
        {'slot_id': 4, 'symbol_internal_id': 7, 'name': 'Symbol 7', 'img_link': '/slot4/sprite_6.png', 'value_multiplier': 20},
        {'slot_id': 4, 'symbol_internal_id': 8, 'name': 'Symbol 8', 'img_link': '/slot4/sprite_7.png', 'value_multiplier': 30},
        {'slot_id': 4, 'symbol_internal_id': 9, 'name': 'Symbol 9', 'img_link': '/slot4/sprite_8.png', 'value_multiplier': 40},
        {'slot_id': 4, 'symbol_internal_id': 10, 'name': 'Symbol 10', 'img_link': '/slot4/sprite_9.png', 'value_multiplier': 50},
        {'slot_id': 4, 'symbol_internal_id': 11, 'name': 'Scatter', 'img_link': '/slot4/sprite_10.png', 'value_multiplier': 0},
        {'slot_id': 4, 'symbol_internal_id': 12, 'name': 'Wild', 'img_link': '/slot4/sprite_0.png', 'value_multiplier': 0}
    ]
    
    op.bulk_insert(slot_symbol_table, slot4_symbols)

    # Insert Slot 4 Bet Options
    slot4_bets = [
        {'slot_id': 4, 'bet_amount': 10},
        {'slot_id': 4, 'bet_amount': 20},
        {'slot_id': 4, 'bet_amount': 50},
        {'slot_id': 4, 'bet_amount': 100},
        {'slot_id': 4, 'bet_amount': 200},
        {'slot_id': 4, 'bet_amount': 500}
    ]
    
    op.bulk_insert(slot_bet_table, slot4_bets)


def downgrade():
    # Delete all data for the 4 slots in reverse order
    op.execute("DELETE FROM slot_bet WHERE slot_id IN (1, 2, 3, 4)")
    op.execute("DELETE FROM slot_symbol WHERE slot_id IN (1, 2, 3, 4)")
    op.execute("DELETE FROM slot WHERE id IN (1, 2, 3, 4)")