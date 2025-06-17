export default class SoundManager {
    constructor(scene) {
        this.scene = scene;
        this.sounds = {};
        this.volume = 0.5;
        this.muted = false;
        
        // Initialize sound effects
        this.initializeSounds();
    }

    initializeSounds() {
        // Common casino sounds
        this.createSound('chipPlace', this.generateChipPlaceSound());
        this.createSound('chipClick', this.generateChipClickSound());
        this.createSound('chipStack', this.generateChipStackSound());
        this.createSound('cardFlip', this.generateCardFlipSound());
        this.createSound('cardDeal', this.generateCardDealSound());
        this.createSound('cardShuffle', this.generateCardShuffleSound());
        this.createSound('wheelSpin', this.generateWheelSpinSound());
        this.createSound('ballRoll', this.generateBallRollSound());
        this.createSound('win', this.generateWinSound());
        this.createSound('bigWin', this.generateBigWinSound());
        this.createSound('lose', this.generateLoseSound());
        this.createSound('buttonClick', this.generateButtonClickSound());
        this.createSound('hover', this.generateHoverSound());
        this.createSound('error', this.generateErrorSound());
        this.createSound('success', this.generateSuccessSound());
        this.createSound('ambient', this.generateAmbientSound());
        
        // Slot machine specific sounds
        this.createSound('reelSpin', this.generateReelSpinSound());
        this.createSound('reelStop', this.generateReelStopSound());
        this.createSound('payline', this.generatePaylineSound());
        this.createSound('jackpot', this.generateJackpotSound());
        
        // Poker specific sounds
        this.createSound('fold', this.generateFoldSound());
        this.createSound('call', this.generateCallSound());
        this.createSound('raise', this.generateRaiseSound());
        this.createSound('allIn', this.generateAllInSound());
        
        // Blackjack specific sounds
        this.createSound('hit', this.generateHitSound());
        this.createSound('stand', this.generateStandSound());
        this.createSound('double', this.generateDoubleSound());
        this.createSound('split', this.generateSplitSound());
        this.createSound('blackjack', this.generateBlackjackSound());
        this.createSound('bust', this.generateBustSound());
        
        // Baccarat specific sounds
        this.createSound('playerWin', this.generatePlayerWinSound());
        this.createSound('bankerWin', this.generateBankerWinSound());
        this.createSound('tie', this.generateTieSound());
        
        // Spacecrash specific sounds
        this.createSound('rocketLaunch', this.generateRocketLaunchSound());
        this.createSound('rocketFly', this.generateRocketFlySound());
        this.createSound('explosion', this.generateExplosionSound());
        this.createSound('eject', this.generateEjectSound());
    }

    createSound(key, audioBuffer) {
        if (this.scene.sound.context) {
            try {
                // Create audio buffer source
                const audioData = this.scene.sound.add(key, {
                    volume: this.volume,
                    loop: false
                });
                
                this.sounds[key] = audioData;
            } catch (error) {
                console.warn(`Failed to create sound ${key}:`, error);
                // Create a silent fallback
                this.sounds[key] = {
                    play: () => {},
                    stop: () => {},
                    setVolume: () => {}
                };
            }
        }
    }

    playSound(key, options = {}) {
        if (this.muted) return;
        
        const sound = this.sounds[key];
        if (sound && sound.play) {
            try {
                sound.play({
                    volume: (options.volume || 1) * this.volume,
                    rate: options.rate || 1,
                    detune: options.detune || 0,
                    seek: options.seek || 0,
                    delay: options.delay || 0,
                    loop: options.loop || false
                });
            } catch (error) {
                console.warn(`Failed to play sound ${key}:`, error);
            }
        }
    }

    stopSound(key) {
        const sound = this.sounds[key];
        if (sound && sound.stop) {
            sound.stop();
        }
    }

    stopAllSounds() {
        Object.values(this.sounds).forEach(sound => {
            if (sound.stop) {
                sound.stop();
            }
        });
    }

    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        Object.values(this.sounds).forEach(sound => {
            if (sound.setVolume) {
                sound.setVolume(this.volume);
            }
        });
    }

    setMuted(muted) {
        this.muted = muted;
        if (muted) {
            this.stopAllSounds();
        }
    }

    // Sound generation methods using Web Audio API
    generateChipPlaceSound() {
        return this.createToneSequence([
            { frequency: 800, duration: 0.05, volume: 0.3 },
            { frequency: 600, duration: 0.05, volume: 0.2 },
            { frequency: 400, duration: 0.1, volume: 0.1 }
        ]);
    }

    generateChipClickSound() {
        return this.createToneSequence([
            { frequency: 1200, duration: 0.02, volume: 0.2 },
            { frequency: 900, duration: 0.03, volume: 0.1 }
        ]);
    }

    generateChipStackSound() {
        return this.createToneSequence([
            { frequency: 600, duration: 0.08, volume: 0.3 },
            { frequency: 700, duration: 0.08, volume: 0.25 },
            { frequency: 800, duration: 0.08, volume: 0.2 },
            { frequency: 900, duration: 0.08, volume: 0.15 }
        ]);
    }

    generateCardFlipSound() {
        return this.createNoiseSequence([
            { type: 'white', duration: 0.05, volume: 0.15, filter: 2000 },
            { type: 'pink', duration: 0.03, volume: 0.1, filter: 1500 }
        ]);
    }

    generateCardDealSound() {
        return this.createNoiseSequence([
            { type: 'white', duration: 0.08, volume: 0.2, filter: 1800 },
            { type: 'brown', duration: 0.05, volume: 0.1, filter: 1200 }
        ]);
    }

    generateCardShuffleSound() {
        return this.createNoiseSequence([
            { type: 'white', duration: 1.0, volume: 0.15, filter: 2500, modulation: true }
        ]);
    }

    generateWheelSpinSound() {
        return this.createToneSequence([
            { frequency: 200, duration: 3.0, volume: 0.3, modulation: 'tremolo' },
            { frequency: 150, duration: 2.0, volume: 0.2, modulation: 'tremolo' }
        ]);
    }

    generateBallRollSound() {
        return this.createToneSequence([
            { frequency: 300, duration: 2.0, volume: 0.2, modulation: 'vibrato' }
        ]);
    }

    generateWinSound() {
        return this.createToneSequence([
            { frequency: 523, duration: 0.2, volume: 0.4 }, // C5
            { frequency: 659, duration: 0.2, volume: 0.4 }, // E5
            { frequency: 784, duration: 0.3, volume: 0.5 }  // G5
        ]);
    }

    generateBigWinSound() {
        return this.createToneSequence([
            { frequency: 523, duration: 0.15, volume: 0.5 }, // C5
            { frequency: 659, duration: 0.15, volume: 0.5 }, // E5
            { frequency: 784, duration: 0.15, volume: 0.5 }, // G5
            { frequency: 1047, duration: 0.4, volume: 0.6 }  // C6
        ]);
    }

    generateLoseSound() {
        return this.createToneSequence([
            { frequency: 400, duration: 0.15, volume: 0.3 },
            { frequency: 350, duration: 0.15, volume: 0.25 },
            { frequency: 300, duration: 0.2, volume: 0.2 }
        ]);
    }

    generateButtonClickSound() {
        return this.createToneSequence([
            { frequency: 1000, duration: 0.03, volume: 0.2 },
            { frequency: 800, duration: 0.02, volume: 0.1 }
        ]);
    }

    generateHoverSound() {
        return this.createToneSequence([
            { frequency: 1200, duration: 0.01, volume: 0.1 }
        ]);
    }

    generateErrorSound() {
        return this.createToneSequence([
            { frequency: 200, duration: 0.2, volume: 0.3 },
            { frequency: 180, duration: 0.2, volume: 0.25 },
            { frequency: 160, duration: 0.3, volume: 0.2 }
        ]);
    }

    generateSuccessSound() {
        return this.createToneSequence([
            { frequency: 523, duration: 0.1, volume: 0.3 },
            { frequency: 784, duration: 0.2, volume: 0.4 }
        ]);
    }

    generateAmbientSound() {
        return this.createNoiseSequence([
            { type: 'pink', duration: 60.0, volume: 0.05, filter: 500, loop: true }
        ]);
    }

    generateReelSpinSound() {
        return this.createToneSequence([
            { frequency: 100, duration: 2.0, volume: 0.25, modulation: 'tremolo' }
        ]);
    }

    generateReelStopSound() {
        return this.createToneSequence([
            { frequency: 400, duration: 0.1, volume: 0.3 },
            { frequency: 300, duration: 0.05, volume: 0.2 }
        ]);
    }

    generatePaylineSound() {
        return this.createToneSequence([
            { frequency: 659, duration: 0.1, volume: 0.3 },
            { frequency: 784, duration: 0.1, volume: 0.3 },
            { frequency: 1047, duration: 0.2, volume: 0.4 }
        ]);
    }

    generateJackpotSound() {
        return this.createToneSequence([
            { frequency: 523, duration: 0.1, volume: 0.5 },
            { frequency: 659, duration: 0.1, volume: 0.5 },
            { frequency: 784, duration: 0.1, volume: 0.5 },
            { frequency: 1047, duration: 0.1, volume: 0.6 },
            { frequency: 1319, duration: 0.3, volume: 0.7 }
        ]);
    }

    generateFoldSound() {
        return this.createNoiseSequence([
            { type: 'white', duration: 0.1, volume: 0.15, filter: 1500 }
        ]);
    }

    generateCallSound() {
        return this.createToneSequence([
            { frequency: 600, duration: 0.1, volume: 0.3 },
            { frequency: 500, duration: 0.1, volume: 0.2 }
        ]);
    }

    generateRaiseSound() {
        return this.createToneSequence([
            { frequency: 700, duration: 0.1, volume: 0.3 },
            { frequency: 800, duration: 0.1, volume: 0.3 },
            { frequency: 900, duration: 0.1, volume: 0.3 }
        ]);
    }

    generateAllInSound() {
        return this.createToneSequence([
            { frequency: 800, duration: 0.15, volume: 0.4 },
            { frequency: 1000, duration: 0.15, volume: 0.4 },
            { frequency: 1200, duration: 0.2, volume: 0.5 }
        ]);
    }

    generateHitSound() {
        return this.createNoiseSequence([
            { type: 'white', duration: 0.06, volume: 0.2, filter: 1800 }
        ]);
    }

    generateStandSound() {
        return this.createToneSequence([
            { frequency: 400, duration: 0.1, volume: 0.25 }
        ]);
    }

    generateDoubleSound() {
        return this.createToneSequence([
            { frequency: 600, duration: 0.08, volume: 0.3 },
            { frequency: 800, duration: 0.08, volume: 0.3 }
        ]);
    }

    generateSplitSound() {
        return this.createToneSequence([
            { frequency: 500, duration: 0.05, volume: 0.25 },
            { frequency: 700, duration: 0.05, volume: 0.25 }
        ]);
    }

    generateBlackjackSound() {
        return this.createToneSequence([
            { frequency: 659, duration: 0.15, volume: 0.4 },
            { frequency: 784, duration: 0.15, volume: 0.4 },
            { frequency: 1047, duration: 0.3, volume: 0.5 }
        ]);
    }

    generateBustSound() {
        return this.createToneSequence([
            { frequency: 300, duration: 0.2, volume: 0.3 },
            { frequency: 250, duration: 0.2, volume: 0.25 },
            { frequency: 200, duration: 0.3, volume: 0.2 }
        ]);
    }

    generatePlayerWinSound() {
        return this.createToneSequence([
            { frequency: 523, duration: 0.2, volume: 0.4 },
            { frequency: 659, duration: 0.3, volume: 0.4 }
        ]);
    }

    generateBankerWinSound() {
        return this.createToneSequence([
            { frequency: 440, duration: 0.2, volume: 0.4 },
            { frequency: 523, duration: 0.3, volume: 0.4 }
        ]);
    }

    generateTieSound() {
        return this.createToneSequence([
            { frequency: 392, duration: 0.15, volume: 0.3 },
            { frequency: 440, duration: 0.15, volume: 0.3 },
            { frequency: 523, duration: 0.15, volume: 0.3 }
        ]);
    }

    generateRocketLaunchSound() {
        return this.createNoiseSequence([
            { type: 'white', duration: 1.0, volume: 0.3, filter: 800, modulation: true }
        ]);
    }

    generateRocketFlySound() {
        return this.createToneSequence([
            { frequency: 150, duration: 5.0, volume: 0.2, modulation: 'vibrato' }
        ]);
    }

    generateExplosionSound() {
        return this.createNoiseSequence([
            { type: 'white', duration: 0.5, volume: 0.4, filter: 200 },
            { type: 'brown', duration: 1.0, volume: 0.3, filter: 100 }
        ]);
    }

    generateEjectSound() {
        return this.createToneSequence([
            { frequency: 1000, duration: 0.05, volume: 0.3 },
            { frequency: 800, duration: 0.05, volume: 0.25 },
            { frequency: 600, duration: 0.1, volume: 0.2 }
        ]);
    }

    // Helper methods for sound generation
    createToneSequence(tones) {
        // This would typically use Web Audio API to generate actual audio buffers
        // For now, returning a mock object that represents the audio data
        return {
            type: 'tone',
            sequence: tones,
            duration: tones.reduce((total, tone) => total + tone.duration, 0)
        };
    }

    createNoiseSequence(noises) {
        // This would typically use Web Audio API to generate actual noise buffers
        return {
            type: 'noise',
            sequence: noises,
            duration: noises.reduce((total, noise) => total + noise.duration, 0)
        };
    }

    // Enhanced sound effects for specific game events
    playWinSequence(winAmount) {
        if (winAmount > 1000) {
            this.playSound('bigWin');
            setTimeout(() => this.playSound('jackpot'), 500);
        } else if (winAmount > 100) {
            this.playSound('win');
        } else {
            this.playSound('success');
        }
    }

    playCardDealSequence(numCards, delay = 150) {
        for (let i = 0; i < numCards; i++) {
            setTimeout(() => {
                this.playSound('cardDeal', { volume: 0.8 });
            }, i * delay);
        }
    }

    playChipStackSequence(numChips, delay = 100) {
        for (let i = 0; i < numChips; i++) {
            setTimeout(() => {
                this.playSound('chipPlace', { 
                    volume: 0.7,
                    rate: 0.9 + (i * 0.02) // Slightly increase pitch with each chip
                });
            }, i * delay);
        }
    }

    playSpinSequence(duration = 3000) {
        this.playSound('reelSpin');
        
        // Play reel stop sounds at intervals
        const numReels = 5;
        const stopInterval = duration / numReels;
        
        for (let i = 0; i < numReels; i++) {
            setTimeout(() => {
                this.playSound('reelStop', { 
                    volume: 0.6,
                    rate: 1 + (i * 0.1)
                });
            }, stopInterval * (i + 1));
        }
    }

    destroy() {
        this.stopAllSounds();
        this.sounds = {};
    }
}
