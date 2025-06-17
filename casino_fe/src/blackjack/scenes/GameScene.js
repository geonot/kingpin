import Phaser from 'phaser';

const CARD_WIDTH = 80;
const CARD_HEIGHT = 116;

export default class GameScene extends Phaser.Scene {
  constructor() {
    super({ key: 'GameScene' });

    // Game state properties
    this.eventBus = null;
    this.tableAPIData = null;
    this.gameDefinition = null;
    this.soundEnabled = true;
    this.currentBlackjackHandId = null;

    // Phaser display object properties
    this.playerHandContainers = []; // Array of Phaser.Containers for each player hand
    this.playerScoreTexts = [];     // Array of Phaser.GameObjects.Text for each player hand score
    this.dealerHandContainer = null; // Phaser.Container for dealer's hand
    this.dealerScoreText = null;     // Phaser.GameObjects.Text for dealer's score

    this.outcomeTextObjects = []; // To store text objects displaying win/loss/push per hand
  }

  // --- Scene Lifecycle Methods ---
  create() {
    console.log('GameScene: create() called');
    
    this.eventBus = this.registry.get('eventBus');
    this.tableAPIData = this.registry.get('tableAPIData');
    this.gameDefinition = this.registry.get('gameDefinition');
    this.soundEnabled = this.registry.get('soundEnabled') ?? true;

    if (!this.eventBus || !this.tableAPIData || !this.gameDefinition) {
      console.error('GameScene: Critical data not found in registry. Aborting scene creation.');
      this.eventBus?.emit('phaserBlackjackError', 'Critical data missing for game initialization.');
      return;
    }

    this.createBackgroundAndTable();

    // Register EventBus listeners
    this.eventBus.on('initialDeal', this.handleInitialDeal, this);
    this.eventBus.on('actionResult', this.handleActionResult, this);
    this.eventBus.on('userBalanceUpdate', (newBalance) => {
        this.registry.set('userBalance', newBalance);
    }, this);

    this.eventBus.emit('gameSceneReady');
    console.log('GameScene: Ready. Waiting for initial deal.');
  }

  // --- Core UI and Game Element Creation ---
  createBackgroundAndTable() {
    const { width, height } = this.cameras.main;
    this.add.image(width / 2, height / 2, 'blackjack-background').setOrigin(0.5, 0.5);
    this.add.image(width / 2, height / 2, 'blackjack-table').setOrigin(0.5, 0.5);
  }

  // --- Event Handlers ---
  handleInitialDeal(handData) {
    console.log('GameScene: handleInitialDeal', handData);
    this.resetScene();
    this.currentBlackjackHandId = handData.id;

    const dealerPos = this.gameDefinition.positions.dealer;
    if (!this.dealerHandContainer) {
      this.dealerHandContainer = this.add.container(dealerPos.x, dealerPos.y);
    }
    this.displayDealerHand(handData.dealer_hand, true);

    handData.player_hands.forEach((playerHandData, index) => {
      this.displayPlayerHand(playerHandData, index, handData.player_hands.length);
    });

    this.highlightActiveHand(handData.active_hand_index);
    this.playSound('snd-card-deal');
    this.eventBus.emit('updateButtonStates', handData);
  }

  handleActionResult(resultData) {
    console.log('GameScene: handleActionResult', resultData);
    this.currentBlackjackHandId = resultData.id;

    this.playerHandContainers.forEach(container => container.destroy());
    this.playerScoreTexts.forEach(text => text.destroy());
    this.outcomeTextObjects.forEach(text => text.destroy());
    this.playerHandContainers = [];
    this.playerScoreTexts = [];
    this.outcomeTextObjects = [];

    this.displayDealerHand(resultData.dealer_hand, false);

    resultData.player_hands.forEach((playerHandData, index) => {
      this.displayPlayerHand(playerHandData, index, resultData.player_hands.length);
    });

    if (resultData.status === 'completed') {
      this.displayRoundOutcome(resultData);
      this.playSoundForResult(resultData);
    } else {
      this.highlightActiveHand(resultData.active_hand_index);
    }
    this.eventBus.emit('updateButtonStates', resultData);
  }

  // --- Display Logic for Hands ---
  displayPlayerHand(playerHandData, index, totalPlayerHands) {
    const playerBasePos = this.gameDefinition.positions.player;
    const handSpacingX = this.gameDefinition.positions.player.handSpacingX || (CARD_WIDTH * 1.5);
    const totalWidthOfHands = (totalPlayerHands -1) * handSpacingX;
    const startX = playerBasePos.x - totalWidthOfHands / 2;
    
    const handX = startX + (index * handSpacingX);
    const handY = playerBasePos.y;

    let container = this.playerHandContainers[index];
    if (!container || !container.scene) { // Check if container exists and belongs to this scene
      container = this.add.container(handX, handY);
      this.playerHandContainers[index] = container;
    } else {
      container.removeAll(true);
      container.setPosition(handX, handY);
    }

    playerHandData.cards.forEach((cardString, cardIndex) => {
      const textureKey = this.getCardTextureKey(cardString);
      const cardSprite = this.add.sprite(0, 0, textureKey)
        .setDisplaySize(CARD_WIDTH, CARD_HEIGHT)
        .setOrigin(0.5, 0.5);
      container.add(cardSprite);
      this.animateCardDeal(cardSprite, 0, 0, cardIndex * (this.gameDefinition.animations.dealSpeed / 4 || 100), container);
    });
    this.positionCardsInContainer(container, this.gameDefinition.positions.player.spacing || (CARD_WIDTH * 0.4));

    let scoreText = this.playerScoreTexts[index];
    const scoreTextYOffset = CARD_HEIGHT / 2 + 20;
    if (!scoreText || !scoreText.scene) {
      scoreText = this.make.text({
        x: handX,
        y: handY + scoreTextYOffset,
        text: '',
        style: this.gameDefinition.fontStyles.scoreText
      }).setOrigin(0.5);
      this.playerScoreTexts[index] = scoreText;
    } else {
        scoreText.setPosition(handX, handY + scoreTextYOffset);
    }
    scoreText.setText(`Score: ${playerHandData.total || '0'}`);
    if (playerHandData.is_busted) scoreText.setText(`Bust! (${playerHandData.total})`).setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
    else if (playerHandData.is_blackjack) scoreText.setText(`Blackjack!`).setColor(this.gameDefinition.fontStyles.successColor || '#00ff00');
    else scoreText.setColor(this.gameDefinition.fontStyles.scoreText.fill || '#ffffff');


    let statusText = container.getData('statusText');
    if(!statusText || !statusText.scene) {
        statusText = this.add.text(0, -CARD_HEIGHT / 2 - 15, '', this.gameDefinition.fontStyles.statusText).setOrigin(0.5);
        container.add(statusText);
        container.setData('statusText', statusText);
    }
    statusText.setText('');
    if (playerHandData.is_busted) statusText.setText('BUSTED').setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
    else if (playerHandData.is_blackjack) statusText.setText('BLACKJACK!').setColor(this.gameDefinition.fontStyles.successColor || '#00D700');
    else if (playerHandData.is_standing) statusText.setText('STANDS').setColor(this.gameDefinition.fontStyles.infoColor || '#00FFFF');
    else statusText.setColor(this.gameDefinition.fontStyles.statusText.fill || '#ffffff');
  }

  displayDealerHand(dealerHandData, isInitialDeal) {
    const dealerPos = this.gameDefinition.positions.dealer;
    if (!this.dealerHandContainer || !this.dealerHandContainer.scene) {
      this.dealerHandContainer = this.add.container(dealerPos.x, dealerPos.y);
    }
    this.dealerHandContainer.removeAll(true);

    dealerHandData.cards.forEach((cardString, index) => {
      const textureKey = (isInitialDeal && index === 1 && cardString === 'FACE_DOWN') ? 'card-back' : this.getCardTextureKey(cardString);
      const cardSprite = this.add.sprite(0,0, textureKey)
        .setDisplaySize(CARD_WIDTH, CARD_HEIGHT)
        .setOrigin(0.5, 0.5);
      this.dealerHandContainer.add(cardSprite);
      this.animateCardDeal(cardSprite, 0, 0, index * (this.gameDefinition.animations.dealSpeed / 4 || 100), this.dealerHandContainer);
    });
    this.positionCardsInContainer(this.dealerHandContainer, this.gameDefinition.positions.dealer.spacing || (CARD_WIDTH * 0.4));

    const scoreTextYOffset = CARD_HEIGHT / 2 + 20;
    if (!this.dealerScoreText || !this.dealerScoreText.scene) {
      this.dealerScoreText = this.make.text({
        x: dealerPos.x,
        y: dealerPos.y + scoreTextYOffset,
        text: '',
        style: this.gameDefinition.fontStyles.scoreText
      }).setOrigin(0.5);
    }
    this.dealerScoreText.setText(`Dealer: ${dealerHandData.total || '?'}`);
    if (dealerHandData.is_busted) this.dealerScoreText.setText(`Dealer Busts! (${dealerHandData.total})`).setColor(this.gameDefinition.fontStyles.errorColor || '#ff0000');
    else if (dealerHandData.is_blackjack) this.dealerScoreText.setText(`Dealer Blackjack!`).setColor(this.gameDefinition.fontStyles.successColor || '#00D700');
    else this.dealerScoreText.setColor(this.gameDefinition.fontStyles.scoreText.fill || '#ffffff');
  }

  animateCardDeal(cardSprite, finalXInContainer, finalYInContainer, delay, container) {
    const dealSpeed = this.gameDefinition.animations.dealSpeed || 500;
    const deckPosition = this.gameDefinition.positions.deck;
    const startX = deckPosition.x - container.x;
    const startY = deckPosition.y - container.y;

    cardSprite.setPosition(startX, startY);
    cardSprite.setAlpha(0.3);
    cardSprite.setScale(0.8);

    // Enhanced card deal animation with effects
    this.tweens.add({
      targets: cardSprite,
      x: finalXInContainer,
      y: finalYInContainer,
      alpha: 1,
      scaleX: 1,
      scaleY: 1,
      delay: delay,
      duration: dealSpeed,
      ease: 'Back.easeOut',
      onComplete: () => {
        // Add subtle sparkle effect when card lands
        this.createCardLandEffect(container.x + finalXInContainer, container.y + finalYInContainer);
      }
    });
  }

  createCardLandEffect(x, y) {
    // Simple sparkle effect
    for (let i = 0; i < 3; i++) {
      const sparkle = this.add.circle(x, y, 2, 0xFFD700);
      
      this.tweens.add({
        targets: sparkle,
        x: x + (Math.random() - 0.5) * 20,
        y: y + (Math.random() - 0.5) * 20,
        alpha: 0,
        duration: 200,
        delay: i * 30,
        onComplete: () => sparkle.destroy()
      });
    }
  }

  positionCardsInContainer(container, cardSpacing) {
    let currentX = 0;
    const numCards = container.list.filter(obj => obj instanceof Phaser.GameObjects.Sprite).length;
    currentX = -( (numCards -1) * cardSpacing) / 2;

    container.list.forEach((card) => {
      if (card instanceof Phaser.GameObjects.Sprite) {
        card.x = currentX;
        currentX += cardSpacing;
      }
    });
  }

  highlightActiveHand(activeIndex) {
    this.playerHandContainers.forEach((container, index) => {
      if (container.getData('highlightIndicator')) {
          container.getData('highlightIndicator').destroy();
          container.setData('highlightIndicator', null);
      }
      container.setScale(1); // Reset scale

      if (index === activeIndex && container.scene) { // Check if container is still valid
        const highlightColor = this.gameDefinition.colors.highlightColor || 0xFFD700;
        const highlightThickness = 4;

        // Create a graphics object for border - relative to container
        const firstCard = container.list.find(c => c instanceof Phaser.GameObjects.Sprite);
        if (!firstCard) return;

        // Calculate width of all cards in container
        const numCards = container.list.filter(obj => obj instanceof Phaser.GameObjects.Sprite).length;
        const spacing = this.gameDefinition.positions.player.spacing || (CARD_WIDTH * 0.4);
        const totalCardsWidth = CARD_WIDTH + (numCards - 1) * spacing;

        const box = this.add.graphics();
        box.lineStyle(highlightThickness, highlightColor, 0.9);
        // Position relative to container's (0,0) which is center of the hand
        box.strokeRect(
            -totalCardsWidth / 2 - highlightThickness,
            -CARD_HEIGHT / 2 - highlightThickness,
            totalCardsWidth + 2 * highlightThickness,
            CARD_HEIGHT + 2 * highlightThickness
        );
        container.add(box); // Add to container so it moves with it
        container.setData('highlightIndicator', box);
        container.sendToBack(box); // Send highlight behind cards
      }
    });
  }

  displayRoundOutcome(outcomeData) {
    this.outcomeTextObjects.forEach(text => text.destroy());
    this.outcomeTextObjects = [];

    outcomeData.player_hands.forEach((hand, index) => {
      const container = this.playerHandContainers[index];
      if (container && container.scene) {
        let resultText = hand.result ? hand.result.replace('_', ' ').toUpperCase() : 'OUTCOME';
        let textColor = this.gameDefinition.fontStyles.outcomeText.fill || '#ffffff';
        
        // Add win celebration effects
        if (hand.result === 'win' || hand.result === 'blackjack_win') {
          textColor = this.gameDefinition.fontStyles.successColor || '#00D700';
          this.createWinCelebration(container.x, container.y);
          
          if (hand.result === 'blackjack_win') {
            this.createBlackjackCelebration(container.x, container.y);
          }
        } else if (hand.result === 'lose') {
          textColor = this.gameDefinition.fontStyles.errorColor || '#ff0000';
        } else if (hand.result === 'push') {
          textColor = this.gameDefinition.fontStyles.infoColor || '#ffff00';
        }

        const outcomeText = this.add.text(
          0, // Centered in container
          CARD_HEIGHT / 2 + 45,
          resultText,
          { ...this.gameDefinition.fontStyles.outcomeText, fill: textColor }
        ).setOrigin(0.5);
        
        // Animate outcome text
        outcomeText.setScale(0);
        this.tweens.add({
          targets: outcomeText,
          scaleX: 1,
          scaleY: 1,
          duration: 300,
          ease: 'Back.easeOut'
        });
        
        container.add(outcomeText);
        this.outcomeTextObjects.push(outcomeText);
      }
    });
    
    this.eventBus.emit('roundEndedUI', outcomeData);
  }

  createWinCelebration(x, y) {
    // Create golden particles
    for (let i = 0; i < 8; i++) {
      const particle = this.add.circle(x, y, 4, 0xFFD700);
      
      const angle = (i / 8) * Math.PI * 2;
      const distance = 50 + Math.random() * 30;
      
      this.tweens.add({
        targets: particle,
        x: x + Math.cos(angle) * distance,
        y: y + Math.sin(angle) * distance,
        alpha: 0,
        scaleX: 0.5,
        scaleY: 0.5,
        duration: 800,
        delay: i * 50,
        onComplete: () => particle.destroy()
      });
    }
  }

  createBlackjackCelebration(x, y) {
    // Special blackjack celebration with bigger effect
    const text = this.add.text(x, y - 50, 'BLACKJACK!', {
      fontSize: '24px',
      fontFamily: 'Arial',
      fill: '#FFD700',
      fontStyle: 'bold'
    }).setOrigin(0.5);
    
    // Animate special text
    text.setScale(0);
    this.tweens.add({
      targets: text,
      scaleX: 1.5,
      scaleY: 1.5,
      duration: 300,
      ease: 'Back.easeOut',
      yoyo: true,
      repeat: 2,
      onComplete: () => text.destroy()
    });
    
    // Extra sparkles for blackjack
    for (let i = 0; i < 15; i++) {
      const sparkle = this.add.circle(x, y, 3, 0xFFFFFF);
      
      this.tweens.add({
        targets: sparkle,
        x: x + (Math.random() - 0.5) * 100,
        y: y + (Math.random() - 0.5) * 100,
        alpha: 0,
        duration: 1000,
        delay: Math.random() * 300,
        onComplete: () => sparkle.destroy()
      });
    }
  }
  
  playSoundForResult(resultData) {
    // Simplified: play based on first hand's result or if there's a net win amount
    if (!resultData || !resultData.player_hands || resultData.player_hands.length === 0) return;

    const mainHandResult = resultData.player_hands[0].result; // Consider first hand as primary for sound
    
    if (resultData.win_amount > 0) { // Net win across all hands
        if (mainHandResult === 'blackjack_win') this.playSound('snd-blackjack');
        else this.playSound('snd-win');
    } else if (resultData.win_amount < 0) { // Net loss
        this.playSound('snd-lose');
    } else { // Net zero (pushes or balanced win/loss)
        if (mainHandResult === 'push') this.playSound('snd-push');
        // Potentially other sounds for complex scenarios if win_amount is 0 but specific hands won/lost.
    }
  }

  resetScene() {
    console.log('GameScene: resetScene()');
    if (this.dealerHandContainer && this.dealerHandContainer.scene) {
      this.dealerHandContainer.removeAll(true);
    }
    if (this.dealerScoreText && this.dealerScoreText.scene) {
      this.dealerScoreText.destroy();
      this.dealerScoreText = null;
    }

    this.playerHandContainers.forEach(container => {
      if (container && container.scene) container.destroy();
    });
    this.playerHandContainers = [];

    this.playerScoreTexts.forEach(text => {
      if (text && text.scene) text.destroy();
    });
    this.playerScoreTexts = [];

    this.outcomeTextObjects.forEach(text => {
      if (text && text.scene) text.destroy();
    });
    this.outcomeTextObjects = [];
  }

  getCardTextureKey(cardString) {
    if (cardString === 'FACE_DOWN' || !cardString || cardString.length < 2) {
      return 'card-back';
    }
    // Card string from backend is SuitRank e.g. "SA", "H2", "DT" (Diamond Ten)
    // Texture keys in PreloadScene are card-RankSuit e.g. card-AS, card-2H, card-TD
    const suit = cardString[0];
    const rank = cardString.substring(1);
    return `card-${rank}${suit}`;
  }

  playSound(key) {
    if (this.soundEnabled && key && this.sound.get(key)) {
      this.sound.play(key);
    } else if (this.soundEnabled && key) {
      console.warn(`GameScene: Sound key "${key}" not found or not loaded.`);
    }
  }

  shutdown() {
    console.log('GameScene: shutdown() called');
    if (this.eventBus) {
        this.eventBus.off('initialDeal', this.handleInitialDeal, this);
        this.eventBus.off('actionResult', this.handleActionResult, this);
        this.eventBus.off('userBalanceUpdate');
    }

    this.resetScene(); // Clean up visual elements

    if (this.dealerHandContainer && this.dealerHandContainer.scene) this.dealerHandContainer.destroy();
    // playerHandContainers and playerScoreTexts are destroyed in resetScene

    this.dealerHandContainer = null;
    this.dealerScoreText = null;
    this.playerHandContainers = []; // Already cleared in resetScene, but good practice
    this.playerScoreTexts = [];   // Ditto
    this.outcomeTextObjects = []; // Ditto
  }
}
