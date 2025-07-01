"""
SpaceCrash Real-time Game Loop Service
Handles the real-time game flow for SpaceCrash games
"""

import asyncio
import threading
import time
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from flask import current_app
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from ..models import SpacecrashGame, SpacecrashBet, User, db
from ..utils import spacecrash_handler
from ..schemas import SpacecrashGameSchema, SpacecrashPlayerBetSchema

logger = logging.getLogger(__name__)

class SpacecrashGameLoop:
    """Manages real-time SpaceCrash game flow with WebSocket broadcasting"""
    
    def __init__(self, websocket_manager=None, app=None):
        self.websocket_manager = websocket_manager
        self.app = app
        self.running = False
        self.loop_thread = None
        self.current_game_id = None
        
        # Game timing configuration
        self.BETTING_PHASE_DURATION = 10  # seconds
        self.MIN_GAME_DURATION = 3       # minimum seconds before crash
        self.MAX_GAME_DURATION = 120     # maximum seconds before forced crash
        
        # Database session for background thread
        self.db_session = None
        
    def start(self):
        """Start the game loop in a background thread"""
        if self.running:
            logger.warning("Game loop is already running")
            return
            
        self.running = True
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()
        logger.info("SpaceCrash game loop started")
        
    def stop(self):
        """Stop the game loop"""
        self.running = False
        if self.loop_thread:
            self.loop_thread.join(timeout=5)
        logger.info("SpaceCrash game loop stopped")
        
    def _setup_db_session(self):
        """Setup database session for background thread"""
        if self.app:
            with self.app.app_context():
                # Create a new database session for this thread
                engine = create_engine(self.app.config['SQLALCHEMY_DATABASE_URI'])
                Session = sessionmaker(bind=engine)
                self.db_session = Session()
                
    def _run_loop(self):
        """Main game loop - runs in background thread"""
        with self.app.app_context():
            self._setup_db_session()
            
            try:
                while self.running:
                    try:
                        self._process_game_cycle()
                        time.sleep(1)  # Check every second
                    except Exception as e:
                        logger.error(f"Error in game loop: {e}", exc_info=True)
                        time.sleep(5)  # Wait longer on error
                        
            finally:
                if self.db_session:
                    self.db_session.close()
                    
    def _process_game_cycle(self):
        """Process one cycle of the game state machine"""
        current_game = self._get_current_game()
        
        if not current_game:
            # No game exists, create new one and start betting
            current_game = self._create_and_start_betting()
            
        elif current_game.status == 'pending':
            # Move to betting phase
            self._start_betting_phase(current_game)
            
        elif current_game.status == 'betting':
            # Check if betting phase should end
            self._check_betting_phase_end(current_game)
            
        elif current_game.status == 'in_progress':
            # Update current multiplier and check for crash
            self._update_game_progress(current_game)
            
        elif current_game.status == 'completed':
            # Start new game after a short delay
            self._handle_completed_game(current_game)
            
    def _get_current_game(self) -> Optional[SpacecrashGame]:
        """Get the current active game"""
        return self.db_session.scalar(select(SpacecrashGame).filter(
            SpacecrashGame.status.in_(['pending', 'betting', 'in_progress'])
        ).order_by(SpacecrashGame.created_at.desc()))
        
    def _create_and_start_betting(self) -> SpacecrashGame:
        """Create new game and start betting phase"""
        # Create new game using the game loop's session instead of spacecrash_handler
        server_seed = spacecrash_handler.generate_server_seed()
        public_seed = hashlib.sha256(server_seed.encode('utf-8')).hexdigest()

        new_game = SpacecrashGame(
            server_seed=server_seed,
            public_seed=public_seed,
            nonce=0,
            status='pending',
        )
        self.db_session.add(new_game)
        self.db_session.commit()
        
        # Start betting phase
        spacecrash_handler.start_betting_phase(new_game)
        new_game.betting_start_time = datetime.now(timezone.utc)
        self.db_session.commit()
        
        self.current_game_id = new_game.id
        self._broadcast_game_update(new_game)
        
        logger.info(f"Started new betting phase for game {new_game.id}")
        return new_game
        
    def _start_betting_phase(self, game: SpacecrashGame):
        """Start betting phase for existing pending game"""
        spacecrash_handler.start_betting_phase(game)
        game.betting_start_time = datetime.now(timezone.utc)
        self.db_session.commit()
        
        self._broadcast_game_update(game)
        logger.info(f"Started betting phase for game {game.id}")
        
    def _check_betting_phase_end(self, game: SpacecrashGame):
        """Check if betting phase should end and start game"""
        if not game.betting_start_time:
            return
            
        betting_elapsed = (datetime.now(timezone.utc) - game.betting_start_time).total_seconds()
        
        if betting_elapsed >= self.BETTING_PHASE_DURATION:
            # Check if there are any bets
            bet_count = self.db_session.scalar(select(func.count(SpacecrashBet.id)).filter_by(
                game_id=game.id, status='placed'
            ))
            
            if bet_count > 0:
                # Start the game
                self._start_game_round(game)
            else:
                # No bets, extend betting period or start new game
                logger.info(f"No bets for game {game.id}, extending betting period")
                game.betting_start_time = datetime.now(timezone.utc)
                self.db_session.commit()
                
    def _start_game_round(self, game: SpacecrashGame):
        """Start the actual game round"""
        client_seed = f"client_seed_{int(time.time())}"  # Simple client seed
        nonce = 1
        
        success = spacecrash_handler.start_game_round(game, client_seed, nonce)
        if success:
            self.db_session.commit()
            self._broadcast_game_update(game)
            logger.info(f"Started game round {game.id} - crash point: {game.crash_point}")
        else:
            logger.error(f"Failed to start game round {game.id}")
            
    def _update_game_progress(self, game: SpacecrashGame):
        """Update game progress and check for crash"""
        if not game.game_start_time:
            return
            
        elapsed_seconds = (datetime.now(timezone.utc) - game.game_start_time).total_seconds()
        current_multiplier = spacecrash_handler.get_current_multiplier(game)
        
        # Check if game should crash
        should_crash = (
            current_multiplier >= game.crash_point or
            elapsed_seconds >= self.MAX_GAME_DURATION
        )
        
        if should_crash:
            # End the game
            spacecrash_handler.end_game_round(game)
            self.db_session.commit()
            
            self._broadcast_game_update(game)
            logger.info(f"Game {game.id} crashed at {game.crash_point}x after {elapsed_seconds:.2f}s")
        else:
            # Broadcast current state every second during active game
            self._broadcast_game_update(game, include_current_multiplier=True)
            
    def _handle_completed_game(self, game: SpacecrashGame):
        """Handle completed game, wait a bit then start new one"""
        # Wait 3 seconds after game completion before starting new betting
        if not hasattr(game, '_completion_wait_start'):
            game._completion_wait_start = datetime.now(timezone.utc)
            return
            
        wait_elapsed = (datetime.now(timezone.utc) - game._completion_wait_start).total_seconds()
        if wait_elapsed >= 3:
            # Ready to start new game
            self.current_game_id = None
            
    def _broadcast_game_update(self, game: SpacecrashGame, include_current_multiplier: bool = False):
        """Broadcast game state update via WebSocket"""
        if not self.websocket_manager:
            return
            
        try:
            # Prepare game data
            game_data = SpacecrashGameSchema().dump(game)
            
            # Add current multiplier if game is in progress
            if include_current_multiplier and game.status == 'in_progress':
                game_data['current_multiplier'] = spacecrash_handler.get_current_multiplier(game)
            elif game.status == 'betting':
                game_data['current_multiplier'] = 1.0
            elif game.status == 'completed':
                game_data['current_multiplier'] = game.crash_point
                
            # Add current bets
            bets_query = self.db_session.scalars(select(SpacecrashBet).filter_by(game_id=game.id)).all()
            game_data['player_bets'] = SpacecrashPlayerBetSchema(many=True).dump(bets_query)
            
            # Calculate betting time remaining
            if game.status == 'betting' and game.betting_start_time:
                betting_elapsed = (datetime.now(timezone.utc) - game.betting_start_time).total_seconds()
                time_remaining = max(0, self.BETTING_PHASE_DURATION - betting_elapsed)
                game_data['betting_time_remaining'] = time_remaining
                
            # Broadcast to all connected users
            self.websocket_manager.broadcast_spacecrash_update(game_data)
            
        except Exception as e:
            logger.error(f"Error broadcasting game update: {e}", exc_info=True)

# Global instance
spacecrash_game_loop = SpacecrashGameLoop()

def get_spacecrash_game_loop():
    """Get the global game loop instance"""
    return spacecrash_game_loop
