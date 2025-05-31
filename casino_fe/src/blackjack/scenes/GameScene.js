  import Phaser from 'phaser';
import EventBus from '@/event-bus';

export default class GameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameScene' });

    // Game elements
    this.dealerHandContainer = null;
    this.playerHandContainers = [];
    this.dealerScoreText = null;
    this.playerScoreTexts = [];

    // Game state (local copy, synced with registry)
    this.gameState = {};
    this.gameConfig = {};
    this.soundEnabled = true;
  }

  create() {
    console.log('GameScene: Create');
    this.gameConfig = this.registry.get('gameConfig');
    this.gameState = this.registry.get('gameState');
    this.soundEnabled = this.registry.get('soundEnabled') ?? true;

    if (!this.gameConfig) {
      console.error("GameScene: Game config not found!");
      return;
    }

    // Add background and table
    this.add.image(this.cameras.main.width / 2, this.cameras.main.height / 2, 'background').setOrigin(0.5);
    this.add.image(this.cameras.main.width / 2, this.cameras.main.height / 2, 'table').setOrigin(0.5);

    // Ensure positions property exists
    if (!this.gameConfig.positions) {
      console.warn('GameScene: positions property not found in gameConfig, using default positions');
      this.gameConfig.positions = {
        dealer: {
          x: 400,
          y: 150,
          spacing: 30,
          depth: 1 // Z-index for dealer
        },
        player: {
          x: 400,
          y: 350,
          spacing: 30,
          depth: 2, // Z-index for player
          hands: {
            spacing: 200 // Spacing between split hands
          }
        }
      };
    }

    // Create containers for hands
    this.dealerHandContainer = this.add.container(this.gameConfig.positions.dealer.x, this.gameConfig.positions.dealer.y);
    // Player hands container will be managed dynamically

    // Create score text placeholders
    this.dealerScoreText = this.add.text(this.gameConfig.positions.dealer.x, this.gameConfig.positions.dealer.y - 60, '', {
      font: 'bold 20px Arial', color: '#ffffff', backgroundColor: 'rgba(0,0,0,0.5)', padding: { x: 5, y: 2 }
    }).setOrigin(0.5).setVisible(false);

    // --- Event Listeners ---
    // Listen for initial deal from Vue component
    EventBus.$on('initialDeal', (handData) => {
      this.handleInitialDeal(handData);
    });

    // Listen for action results from Vue component
    EventBus.$on('actionResult', (resultData) => {
      this.handleActionResult(resultData);
    });

    // Handle initial hand data passed from Vue component
    const initialHand = this.registry.get('initialHand');
    if (initialHand) {
      this.handleInitialDeal(initialHand);
    }

    console.log('GameScene: Ready.');
  }

  // --- Game Logic Handlers ---

  handleInitialDeal(handData) {
    console.log('GameScene: Handling initial deal', handData);
    this.resetScene(); // Clear previous round elements

    this.gameState.player_hands = handData.player_hands;
    this.gameState.dealer_hand = handData.dealer_hand;
    this.gameState.isPlaying = true;
    this.gameState.currentHandIndex = 0;

    // Deal dealer cards and ensure they're visible
    this.dealCards(this.dealerHandContainer, handData.dealer_cards, true);
    this.updateDealerCards(handData.dealer_cards);
    this.updateScoreText(this.dealerScoreText, handData.dealer_hand.total, true); // Show dealer's score

    // Deal player cards (initial hand)
    this.createPlayerHandContainer(0); // Create container for the first hand
    this.dealCards(this.playerHandContainers[0], handData.player_hands[0].cards, false);
    this.updatePlayerCards(0, handData.player_hands[0].cards);
    this.updateScoreText(this.playerScoreTexts[0], handData.player_hands[0].total);

    // Check for immediate blackjack
    if (handData.player_hands[0].is_blackjack || handData.dealer_hand.is_blackjack) {
      this.endRound(handData); // Backend determines outcome
    } else {
      // Emit player turn event to UIScene
      this.emitPlayerTurn();
    }
  }

  handleActionResult(resultData) {
    console.log('GameScene: Handling action result', resultData);
    const action = resultData.action_type; // Assuming action_type is part of the result
    const handIndex = resultData.hand_index ?? this.gameState.currentHandIndex;

    // Update game state based on result - keep original naming from backend
    this.gameState.player_hands = resultData.player_hands;
    this.gameState.dealer_hand = resultData.dealer_hand;

    // Emit handUpdated event with the latest hand data - use consistent naming
    EventBus.$emit('handUpdated', {
      player_hands: this.gameState.player_hands,
      current_hand_index: handIndex,
      dealer_hand: this.gameState.dealer_hand
    });

    // Animate card dealt if it was a hit or double
    if ((action === 'hit' || action === 'double') && resultData.card_dealt) {
      const targetContainer = this.playerHandContainers[handIndex];
      this.addCardToHand(targetContainer, resultData.card_dealt, this.gameState.player_hands[handIndex].cards.length - 1);
      this.playSound('card-deal');
      
      // Make sure all player cards are visible
      this.updatePlayerCards(handIndex, this.gameState.player_hands[handIndex].cards);
    }

    // Handle split action - needs more complex animation
    if (action === 'split') {
      this.handleSplitAnimation(resultData);
      this.playSound('card-deal'); // Sound for dealing new cards
    }

    // Update scores - IMPORTANT: Update player score before checking for end conditions
    this.updateScoreText(this.playerScoreTexts[handIndex], this.gameState.player_hands[handIndex].total);
    if (resultData.dealer_hand) { // Dealer hand might update if player stood/busted
        // Show all dealer cards and their total score
        this.updateScoreText(this.dealerScoreText, resultData.dealer_hand.total, true);
        
        // Always update dealer cards to ensure all cards are visible
        // Use dealer_hand.cards instead of dealer_cards to get all cards including hits
        if (resultData.dealer_hand && resultData.dealer_hand.cards) {
            console.log('Updating dealer cards from dealer_hand:', resultData.dealer_hand.cards);
            this.updateDealerCards(resultData.dealer_hand.cards);
        } else if (resultData.dealer_cards) {
            console.log('Updating dealer cards from dealer_cards:', resultData.dealer_cards);
            this.updateDealerCards(resultData.dealer_cards);
        }
    }

    // Check if the hand/round ended
    if (resultData.status === 'completed') {
      this.endRound(resultData);
    } else if (this.gameState.player_hands[handIndex].is_busted) {
      // Player busted on this hand
      // Move to next hand or dealer's turn
      this.moveToNextHandOrDealer();
    } else if (action === 'stand' || action === 'double') {
      // Player stood or doubled, move to next hand or dealer's turn
      this.moveToNextHandOrDealer();
    } else {
      // Still player's turn on the current hand (e.g., after a hit)
      this.emitPlayerTurn();
    }
  }

  moveToNextHandOrDealer() {
    const nextHandIndex = this.gameState.currentHandIndex + 1;
    if (nextHandIndex < this.gameState.player_hands.length) {
      // Move to the next split hand
      this.gameState.currentHandIndex = nextHandIndex;
      this.highlightActiveHand(this.gameState.currentHandIndex);
      this.emitPlayerTurn();
    } else {
      // All player hands played, backend handles dealer turn implicitly via action result
      console.log("GameScene: All player hands played or stood/busted.");
      // The result from the last stand/double/bust action should contain the final round outcome
    }
  }
  endRound(resultData) {
    console.log('GameScene: Ending round', resultData);
    this.gameState.isPlaying = false;

    // Reveal dealer's hidden card and any additional cards
    console.log('GameScene: Revealing all dealer cards at the end of the round');

    // Update dealer cards to show all cards face up
    // Use dealer_hand.cards instead of dealer_cards to get all cards including hits
    if (resultData.dealer_hand && resultData.dealer_hand.cards) {
        console.log('Ending round: Updating dealer cards from dealer_hand:', resultData.dealer_hand.cards);
        this.updateDealerCards(resultData.dealer_hand.cards);
    } else if (resultData.dealer_cards) {
        console.log('Ending round: Updating dealer cards from dealer_cards:', resultData.dealer_cards);
        this.updateDealerCards(resultData.dealer_cards);
    }

    // Update final scores with the dealer's total score
    this.updateScoreText(this.dealerScoreText, resultData.dealer_hand.total, true);
    // Update player hands and scores
    resultData.player_hands.forEach((hand, index) => {
      // Make sure all player cards are visible
      this.updatePlayerCards(index, hand.cards);
      
      if (this.playerScoreTexts[index]) {
        // For blackjack hands, display "BLACKJACK" text and highlight
        if (hand.is_blackjack) {
          this.playerScoreTexts[index].setText('BLACKJACK!');
          this.playerScoreTexts[index].setStyle({
            font: 'bold 24px Arial',
            color: '#ffdd00',
            stroke: '#000000',
            strokeThickness: 4,
            backgroundColor: 'rgba(0,0,0,0.6)',
            padding: { x: 8, y: 4 }
          });
          
          // Add special animation for blackjack
          this.highlightBlackjackHand(this.playerHandContainers[index]);
        } else {
          this.updateScoreText(this.playerScoreTexts[index], hand.total);
        }
        this.playerScoreTexts[index].setVisible(true);
      }
    });

    // Calculate and display blackjack payout if applicable
    const blackjackHands = resultData.player_hands.filter(hand => hand.is_blackjack);
    if (blackjackHands.length > 0 && resultData.win_amount > 0) {
      const blackjackPayout = this.gameConfig.rules.blackjackPayout || 1.5;
      const originalBet = this.registry.get('currentBet');
      const payoutAmount = originalBet * blackjackPayout;
      
      this.showBlackjackPayoutText(payoutAmount);
    }

    // Play result sound
    this.playResultSound(resultData.result);

    // Emit round ended event to UIScene with blackjack info - use consistent naming
    EventBus.$emit('roundEnded', {
      result: resultData.result,
      win_amount: resultData.win_amount,
      player_hands: resultData.player_hands,
      dealer_hand: resultData.dealer_hand,
      has_blackjack: blackjackHands.length > 0
    });
  }

  // --- Animations and Visuals ---

  resetScene() {
    // Clear existing cards and containers
    this.dealerHandContainer.removeAll(true);
    this.playerHandContainers.forEach(container => container.removeAll(true).destroy());
    this.playerHandContainers = [];
    this.playerScoreTexts.forEach(text => text.destroy());
    this.playerScoreTexts = [];
    this.dealerScoreText.setVisible(false);
    
    // Emit event to clear UI elements in UIScene
    EventBus.$emit('resetUI');
  }

  createPlayerHandContainer(index) {
      // Ensure positions property exists
      if (!this.gameConfig.positions || !this.gameConfig.positions.player) {
          console.warn('GameScene: positions.player property not found in gameConfig, using default positions');
          this.gameConfig.positions = this.gameConfig.positions || {};
          this.gameConfig.positions.player = {
              x: 400,
              y: 350,
              spacing: 30,
              hands: {
                  spacing: 200 // Spacing between split hands
              }
          };
      } else if (!this.gameConfig.positions.player.hands) {
          console.warn('GameScene: positions.player.hands property not found in gameConfig, using default spacing');
          this.gameConfig.positions.player.hands = {
              spacing: 200 // Default spacing between split hands
          };
      }

      const config = this.gameConfig.positions.player;
      const handSpacing = this.gameConfig.positions.player.hands.spacing;
      const totalHands = this.gameState.player_hands?.length || 1;
      const startX = config.x - ((totalHands - 1) * handSpacing) / 2;
      const x = startX + index * handSpacing;
      const y = config.y;

      const container = this.add.container(x, y);
      this.playerHandContainers[index] = container;

      const scoreText = this.add.text(0, -80, '', { // Position relative to container
          font: 'bold 20px Arial', color: '#ffffff', backgroundColor: 'rgba(0,0,0,0.5)', padding: { x: 5, y: 2 }
      }).setOrigin(0.5).setVisible(false);
      container.add(scoreText); // Add score text to the container
      this.playerScoreTexts[index] = scoreText;

      return container;
  }

  dealCards(container, cards, isDealer) {
    // Ensure animations property exists
    if (!this.gameConfig.animations) {
      console.warn('GameScene: animations property not found in gameConfig, using default animations');
      this.gameConfig.animations = {
        dealSpeed: 300,
        flipSpeed: 200,
        moveSpeed: 300
      };
    }

    // Ensure positions.dealer property exists
    if (!this.gameConfig.positions || !this.gameConfig.positions.dealer) {
      console.warn('GameScene: positions.dealer property not found in gameConfig, using default positions');
      this.gameConfig.positions = this.gameConfig.positions || {};
      this.gameConfig.positions.dealer = {
        x: 400,
        y: 150,
        spacing: 30
      };
    } else if (!this.gameConfig.positions.dealer.spacing) {
      console.warn('GameScene: positions.dealer.spacing property not found in gameConfig, using default spacing');
      this.gameConfig.positions.dealer.spacing = 30;
    }

    const dealSpeed = this.gameConfig.animations.dealSpeed;
    const cardSpacing = this.gameConfig.positions.dealer.spacing; // Use dealer spacing for both for simplicity

    cards.forEach((card, index) => {
      const isFaceDown = false; // All cards face up
      const texture = isFaceDown ? 'card-back' : `card-${card.suit}-${card.value}`;
      const cardSprite = this.add.sprite(0, 0, texture) // Start at container origin
        .setDisplaySize(80, 116) // Adjust size as needed
        .setOrigin(0.5);

      container.add(cardSprite);

      // Calculate target position within the container
      const targetX = (index - (cards.length - 1) / 2) * cardSpacing;

      // Animate dealing from off-screen (e.g., top center)
      cardSprite.setPosition(0, -this.cameras.main.height / 2); // Start off-screen top
      this.tweens.add({
        targets: cardSprite,
        x: targetX,
        y: 0, // Target y is container's y
        duration: dealSpeed,
        delay: index * (dealSpeed / 2), // Stagger dealing
        ease: 'Power2',
        onComplete: () => {
          if (!isFaceDown) {
            this.playSound('card-deal');
          }
        }
      });
    });
  }

  addCardToHand(container, card, cardIndex) {
      // Ensure positions.dealer property exists
      if (!this.gameConfig.positions || !this.gameConfig.positions.dealer) {
          console.warn('GameScene: positions.dealer property not found in gameConfig, using default positions');
          this.gameConfig.positions = this.gameConfig.positions || {};
          this.gameConfig.positions.dealer = {
              x: 400,
              y: 150,
              spacing: 30
          };
      } else if (!this.gameConfig.positions.dealer.spacing) {
          console.warn('GameScene: positions.dealer.spacing property not found in gameConfig, using default spacing');
          this.gameConfig.positions.dealer.spacing = 30;
      }

      const cardSpacing = this.gameConfig.positions.dealer.spacing;
      const texture = `card-${card.suit}-${card.value}`;
      const cardSprite = this.add.sprite(0, 0, texture)
        .setDisplaySize(80, 116)
        .setOrigin(0.5);

      container.add(cardSprite);

      // Recalculate positions for all cards in the hand
      const numCards = container.getAll().filter(item => item.type === 'Sprite').length; // Count only card sprites
      container.getAll().forEach((item, index) => {
          if (item.type === 'Sprite') {
              const targetX = (index - (numCards - 1) / 2) * cardSpacing;
              if (index === cardIndex) { // Animate the new card
                  item.setPosition(0, -this.cameras.main.height / 2); // Start off-screen
                  this.tweens.add({
                      targets: item,
                      x: targetX,
                      y: 0,
                      duration: this.gameConfig.animations.dealSpeed,
                      ease: 'Power2'                                                                                                                                                    
                  });
              } else { // Instantly reposition existing cards if needed (or animate smoothly)
                  this.tweens.add({
                      targets: item,
                      x: targetX,
                      duration: this.gameConfig.animations.moveSpeed,
                      ease: 'Sine.easeInOut'
                  });
              }
          }
      });
  }
  animateDealerDraw(finalDealerCards) {
    // Show all dealer cards
    console.log('GameScene: Showing all dealer cards');
    
    // Update dealer cards to show all cards
    // Check if finalDealerCards is an array with a cards property (might be dealer_hand)
    if (finalDealerCards && finalDealerCards.cards) {
        console.log('Animate dealer draw: Using cards from dealer_hand:', finalDealerCards.cards);
        this.updateDealerCards(finalDealerCards.cards);
    } else {
        console.log('Animate dealer draw: Using dealer_cards directly:', finalDealerCards);
        this.updateDealerCards(finalDealerCards);
    }
    
    // Update the dealer's score based on all cards
    const total = this.calculateHandValue(finalDealerCards);
    this.updateScoreText(this.dealerScoreText, total, true);
    
    // Play card deal sound to indicate dealer is drawing cards
    this.playSound('card-deal');
  }

  // Helper function to calculate hand value (similar to backend)
  calculateHandValue(cards) {
      let total = 0;
      let aces = 0;
      
      for (const card of cards) {
          if (card.value === 'A') {
              aces += 1;
              total += 11;
          } else if (['J', 'Q', 'K'].includes(card.value)) {
              total += 10;
          } else {
              total += parseInt(card.value);
          }
      }
      
      // Adjust for aces if total is over 21
      while (total > 21 && aces > 0) {
          total -= 10;  // Convert an ace from 11 to 1
          aces -= 1;
      }
      
      return total;
  }

  flipCard(cardSprite, newTextureKey) {
    // Ensure animations property exists
    if (!this.gameConfig.animations) {
      console.warn('GameScene: animations property not found in gameConfig, using default animations');
      this.gameConfig.animations = {
        dealSpeed: 300,
        flipSpeed: 200,
        moveSpeed: 300
      };
    } else if (!this.gameConfig.animations.flipSpeed) {
      console.warn('GameScene: animations.flipSpeed property not found in gameConfig, using default flipSpeed');
      this.gameConfig.animations.flipSpeed = 200;
    }

    const flipSpeed = this.gameConfig.animations.flipSpeed;

    this.tweens.add({
      targets: cardSprite,
      scaleX: 0,
      duration: flipSpeed / 2,
      ease: 'Linear',
      onComplete: () => {
        cardSprite.setTexture(newTextureKey);
        this.tweens.add({
          targets: cardSprite,
          scaleX: 0.25,
          duration: flipSpeed / 2,
          ease: 'Linear'
        });
      }
    });
  }

  handleSplitAnimation(resultData) {
      const originalHandIndex = resultData.hand_index ?? 0; // Index of the hand that was split
      const originalContainer = this.playerHandContainers[originalHandIndex];
      const originalCards = resultData.player_hands[originalHandIndex].cards;
      const newHandIndex = resultData.player_hands.length - 1; // Index of the newly created hand
      const newHandCards = resultData.player_hands[newHandIndex].cards;

      // 1. Create container for the new hand
      const newContainer = this.createPlayerHandContainer(newHandIndex);

      // 2. Animate the second card moving from original to new container
      const cardToMoveSprite = originalContainer.getAt(1); // Assuming second card sprite
      if (cardToMoveSprite) {
          originalContainer.remove(cardToMoveSprite, false); // Remove without destroying
          newContainer.add(cardToMoveSprite); // Add to new container

          this.tweens.add({
              targets: cardToMoveSprite,
              x: (-0.5 * this.gameConfig.positions.player.spacing), // Target X in new container (first card)
              y: 0,
              duration: this.gameConfig.animations.moveSpeed,
              ease: 'Sine.easeInOut',
              onComplete: () => {
                  // 3. Deal new card to the new hand
                  this.addCardToHand(newContainer, newHandCards[1], 1);
              }
          });
      }

      // 4. Reposition first card in original container
       const firstCardSprite = originalContainer.getAt(0);
       if (firstCardSprite) {
           this.tweens.add({
               targets: firstCardSprite,
               x: (-0.5 * this.gameConfig.positions.player.spacing), // Target X (first card)
               duration: this.gameConfig.animations.moveSpeed,
               ease: 'Sine.easeInOut',
               onComplete: () => {
                   // 5. Deal new card to the original hand
                   this.addCardToHand(originalContainer, originalCards[1], 1);
               }
           });
       }

      // 6. Update scores after animations potentially
      this.updateScoreText(this.playerScoreTexts[originalHandIndex], resultData.player_hands[originalHandIndex].total);
      this.updateScoreText(this.playerScoreTexts[newHandIndex], resultData.player_hands[newHandIndex].total);

      // 7. Reposition all hand containers smoothly
      this.repositionPlayerHands();
  }

  repositionPlayerHands() {
      // Ensure positions.player property exists
      if (!this.gameConfig.positions || !this.gameConfig.positions.player) {
          console.warn('GameScene: positions.player property not found in gameConfig, using default positions');
          this.gameConfig.positions = this.gameConfig.positions || {};
          this.gameConfig.positions.player = {
              x: 400,
              y: 350,
              spacing: 30,
              hands: {
                  spacing: 200 // Spacing between split hands
              }
          };
      } else if (!this.gameConfig.positions.player.hands) {
          console.warn('GameScene: positions.player.hands property not found in gameConfig, using default spacing');
          this.gameConfig.positions.player.hands = {
              spacing: 200 // Default spacing between split hands
          };
      }

      // Ensure animations property exists
      if (!this.gameConfig.animations) {
          console.warn('GameScene: animations property not found in gameConfig, using default animations');
          this.gameConfig.animations = {
              dealSpeed: 300,
              flipSpeed: 200,
              moveSpeed: 300
          };
      } else if (!this.gameConfig.animations.moveSpeed) {
          console.warn('GameScene: animations.moveSpeed property not found in gameConfig, using default moveSpeed');
          this.gameConfig.animations.moveSpeed = 300;
      }

      const config = this.gameConfig.positions.player;
      const handSpacing = this.gameConfig.positions.player.hands.spacing;
      const totalHands = this.playerHandContainers.length;
      const startX = config.x - ((totalHands - 1) * handSpacing) / 2;

      this.playerHandContainers.forEach((container, index) => {
          const targetX = startX + index * handSpacing;
          this.tweens.add({
              targets: container,
              x: targetX,
              duration: this.gameConfig.animations.moveSpeed,
              ease: 'Sine.easeInOut'
          });
      });
  }

  highlightActiveHand(index) {
      // Add a visual indicator (e.g., border, scale tween) to the active hand container
      this.playerHandContainers.forEach((container, i) => {
          // Remove previous highlights
          this.tweens.killTweensOf(container);
          container.setScale(1);

          if (i === index) {
              // Highlight the active hand
              this.tweens.add({
                  targets: container,
                  scale: 1.05,
                  duration: 200,
                  yoyo: true,
                  repeat: -1 // Loop until stopped
              });
          }
      });
  }
updateScoreText(textObject, score, isDealerVisible = true) {
  if (textObject) {
    textObject.setText(score > 0 ? `${score}` : '');
    textObject.setVisible(score > 0 && isDealerVisible);
  }
}

// Add a new method to update dealer cards
  // Add a new method to update player cards
  updatePlayerCards(handIndex, playerCards) {
    // Clear existing cards in the specified hand container
    const container = this.playerHandContainers[handIndex];
    if (!container) return;
    
    // Remove all sprites but keep the score text
    container.getAll().forEach(item => {
      if (item.type === 'Sprite') {
        item.destroy();
      }
    });
    
    console.log(`Updating player hand ${handIndex} with cards:`, playerCards);
    
    // Add all player cards face up
    playerCards.forEach((card, index) => {
      const texture = `card-${card.suit}-${card.value}`;
      console.log(`Adding player card: ${texture}`);
      const cardSprite = this.add.sprite(0, 0, texture)
        .setDisplaySize(80, 116)
        .setOrigin(0.5);
      
      container.add(cardSprite);
      
      // Position cards with proper spacing
      const cardSpacing = this.gameConfig.positions.dealer.spacing;
      const targetX = (index - (playerCards.length - 1) / 2) * cardSpacing;
      cardSprite.setPosition(targetX, 0);
    });
  }
  
updateDealerCards(dealerCards) {
  console.log('updateDealerCards called with:', dealerCards);
  // Clear existing cards but keep track of how many we had
  const previousCardCount = this.dealerHandContainer.getAll().filter(item => item.type === 'Sprite').length;
  console.log(`Previous dealer card count: ${previousCardCount}, New dealer card count: ${dealerCards.length}`);
  
  // Only clear and redraw if we have new cards
  this.dealerHandContainer.removeAll(true);
  
  // Add all dealer cards face up
  dealerCards.forEach((card, index) => {
    const texture = `card-${card.suit}-${card.value}`;
    console.log(`Adding dealer card: ${texture}`);
    const cardSprite = this.add.sprite(0, 0, texture)
      .setDisplaySize(80, 116)
      .setOrigin(0.5);
    
    this.dealerHandContainer.add(cardSprite);
    
    // Position cards with proper spacing
    const cardSpacing = this.gameConfig.positions.dealer.spacing;
    const targetX = (index - (dealerCards.length - 1) / 2) * cardSpacing;
    cardSprite.setPosition(targetX, 0);
  });
}

  emitPlayerTurn() {
      // Ensure rules property exists
      if (!this.gameConfig.rules) {
          console.warn('GameScene: rules property not found in gameConfig, using default rules');
          this.gameConfig.rules = {
              blackjackPayout: 1.5,      // Blackjack pays 3:2
              dealerStandsOn: 'soft17',  // Dealer stands on soft 17
              doubleAfterSplit: true,    // Can double after split
              hitSplitAces: false,       // Cannot hit split aces
              maxSplitHands: 4,          // Maximum number of hands after splits
              insurance: true,           // Insurance offered
              surrenderAllowed: false    // Surrender not allowed
          };
      } else if (!this.gameConfig.rules.maxSplitHands) {
          console.warn('GameScene: rules.maxSplitHands property not found in gameConfig, using default value');
          this.gameConfig.rules.maxSplitHands = 4;
      }

      const currentHand = this.gameState.player_hands[this.gameState.currentHandIndex];
      const canHit = !currentHand.is_busted && !currentHand.is_blackjack;
      const canStand = true; // Always possible unless busted/blackjack
      const canDouble = currentHand.cards.length === 2 && !currentHand.is_split && this.registry.get('userBalance') >= this.registry.get('currentBet'); // Check balance
      const canSplit = currentHand.cards.length === 2 && currentHand.cards[0].value === currentHand.cards[1].value && this.gameState.player_hands.length < this.gameConfig.rules.maxSplitHands && this.registry.get('userBalance') >= this.registry.get('currentBet'); // Check balance

      EventBus.$emit('playerTurn', {
          player_hands: this.gameState.player_hands,
          dealer_hand: this.gameState.dealer_hand,
          canHit,
          canStand,
          canDouble,
          canSplit,
          current_hand_index: this.gameState.currentHandIndex
      });
  }
  playResultSound(result) {
      let soundKey = null;
      switch (result) {
          case 'blackjack': soundKey = 'blackjack'; break;
          case 'win': soundKey = 'win'; break;
          case 'lose': soundKey = 'lose'; break;
          case 'push': soundKey = 'push'; break;
      }
      if (soundKey) {
          this.playSound(soundKey);
      }
  }

  playSound(key) {
    if (this.soundEnabled && this.sound.get(key)) {
      this.sound.play(key);
    } else if (this.soundEnabled) {
        console.warn(`Sound key "${key}" not found or loaded.`);
    }
  }

  showBlackjackPayoutText(payoutAmount) {
    const { width, height } = this.cameras.main;
    
    // Create text for blackjack announcement
    const blackjackText = this.add.text(width / 2, height * 0.5, 'BLACKJACK!', {
      font: 'bold 48px Arial',
      color: '#ffdd00',
      stroke: '#000000',
      strokeThickness: 6,
      shadow: { offsetX: 2, offsetY: 2, color: '#000000', blur: 4, stroke: true, fill: true }
    }).setOrigin(0.5);
    
    // Create text for payout amount
    const payoutText = this.add.text(width / 2, height * 0.5 + 60, `PAYS ${payoutAmount.toFixed(0)} CHIPS`, {
      font: 'bold 32px Arial',
      color: '#ffffff',
      stroke: '#000000',
      strokeThickness: 4
    }).setOrigin(0.5);
    
    // Animation for the blackjack announcement
    this.tweens.add({
      targets: [blackjackText, payoutText],
      scale: { from: 0.5, to: 1 },
      alpha: { from: 0, to: 1 },
      duration: 800,
      ease: 'Back.easeOut',
      onComplete: () => {
        this.time.delayedCall(1500, () => {
          this.tweens.add({
            targets: [blackjackText, payoutText],
            alpha: 0,
            y: '-=50',
            duration: 500,
            onComplete: () => {
              blackjackText.destroy();
              payoutText.destroy();
            }
          });
        });
      }
    });
  }

  highlightBlackjackHand(container) {
    // Create a gold glow effect around the blackjack hand
    const bounds = new Phaser.Geom.Rectangle(-120, -70, 240, 140);
    const glow = this.add.graphics();
    
    glow.lineStyle(4, 0xffdd00, 0.8);
    glow.strokeRectShape(bounds);
    container.add(glow);
    
    // Add particle effect for blackjack
    const emitter = this.add.particles(0, 0, 'particle', {
      frame: 0,
      lifespan: 1000,
      speed: { min: 100, max: 200 },
      scale: { start: 0.5, end: 0 },
      quantity: 1,
      blendMode: 'ADD',
      frequency: 50,
      emitting: true
    });
    
    container.add(emitter);
    
    // Stop particles after 2 seconds
    this.time.delayedCall(2000, () => {
      emitter.stop();
      this.tweens.add({
        targets: glow,
        alpha: 0,
        duration: 500,
        onComplete: () => glow.destroy()
      });
    });
  }
}