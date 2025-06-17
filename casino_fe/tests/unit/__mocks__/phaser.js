// Mock for Phaser.js library
export default {
  Scene: class MockScene {
    constructor(config) {
      this.scene = { key: config?.key || 'MockScene' };
      this.add = {
        image: jest.fn().mockReturnThis(),
        text: jest.fn().mockReturnThis(),
        graphics: jest.fn().mockReturnThis(),
        sprite: jest.fn().mockReturnThis(),
        group: jest.fn().mockReturnThis(),
      };
      this.physics = {
        add: {
          existing: jest.fn().mockReturnThis(),
        },
        world: {
          setBounds: jest.fn(),
        },
      };
      this.input = {
        on: jest.fn(),
        off: jest.fn(),
      };
      this.cameras = {
        main: {
          setBounds: jest.fn(),
        },
      };
      this.load = {
        image: jest.fn(),
        audio: jest.fn(),
        start: jest.fn(),
        on: jest.fn(),
      };
      this.sound = {
        add: jest.fn().mockReturnValue({
          play: jest.fn(),
          stop: jest.fn(),
          setVolume: jest.fn(),
        }),
      };
      this.time = {
        addEvent: jest.fn(),
        delayedCall: jest.fn(),
      };
    }
    
    preload() {}
    create() {}
    update() {}
  },
  
  Game: class MockGame {
    constructor(config) {
      this.config = config;
      this.scene = {
        add: jest.fn(),
        start: jest.fn(),
        stop: jest.fn(),
        remove: jest.fn(),
        get: jest.fn(),
      };
      this.destroy = jest.fn();
    }
  },
  
  AUTO: 'AUTO',
  WEBGL: 'WEBGL',
  CANVAS: 'CANVAS',
  
  Physics: {
    Matter: {
      MatterPhysics: class MockMatterPhysics {},
    },
  },
  
  GameObjects: {
    Graphics: class MockGraphics {
      constructor() {
        this.fillStyle = jest.fn().mockReturnThis();
        this.fillCircle = jest.fn().mockReturnThis();
        this.strokeStyle = jest.fn().mockReturnThis();
        this.lineStyle = jest.fn().mockReturnThis();
        this.strokeCircle = jest.fn().mockReturnThis();
        this.clear = jest.fn().mockReturnThis();
        this.setPosition = jest.fn().mockReturnThis();
      }
    },
    Image: class MockImage {
      constructor() {
        this.setOrigin = jest.fn().mockReturnThis();
        this.setScale = jest.fn().mockReturnThis();
        this.setPosition = jest.fn().mockReturnThis();
        this.setInteractive = jest.fn().mockReturnThis();
        this.on = jest.fn().mockReturnThis();
      }
    },
    Text: class MockText {
      constructor() {
        this.setOrigin = jest.fn().mockReturnThis();
        this.setPosition = jest.fn().mockReturnThis();
        this.setText = jest.fn().mockReturnThis();
        this.setStyle = jest.fn().mockReturnThis();
      }
    },
  },
  
  Input: {
    Events: {
      POINTER_DOWN: 'pointerdown',
      POINTER_UP: 'pointerup',
      POINTER_MOVE: 'pointermove',
    },
  },
  
  Math: {
    Between: jest.fn((min, max) => Math.floor(Math.random() * (max - min + 1)) + min),
    DegToRad: jest.fn((degrees) => degrees * (Math.PI / 180)),
    RadToDeg: jest.fn((radians) => radians * (180 / Math.PI)),
  },
  
  Utils: {
    Array: {
      Shuffle: jest.fn((array) => array),
    },
  },
  
  Textures: {
    Events: {
      READY: 'ready',
    },
  },
};
