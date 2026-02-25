import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
    
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    MAX_IMAGE_DIMENSION = 4000
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    ALLOWED_MIME_TYPES = {
        'image/png',
        'image/jpeg',
        'image/gif',
        'image/bmp',
        'image/webp'
    }
    
    DEFAULT_WIDTH = 100
    DEFAULT_VERTICAL_SCALE = 2
    DEFAULT_ZOOM = 1.0
    DEFAULT_CHARSET = '@%#*+=-:. '
    
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '60 per minute')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_DEFAULT = '30 per minute'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
