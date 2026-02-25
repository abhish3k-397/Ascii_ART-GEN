#!/usr/bin/env python3
import os
import io
import logging
import tempfile
import base64
import uuid
import time
from functools import wraps
from flask import Flask, render_template, request, send_file, jsonify, g
from PIL import Image, ImageDraw, ImageFont
import ascii_converter
from config import config

env = os.getenv('FLASK_ENV', 'production')
app = Flask(__name__)
app.config.from_object(config[env])

os.makedirs(os.path.dirname(app.config['LOG_FILE']), exist_ok=True)

class RequestIdFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = 'N/A'
        return super().format(record)

formatter = RequestIdFormatter(
    '{"time":"%(asctime)s","level":"%(levelname)s","request_id":"%(request_id)s","message":"%(message)s"}'
)

file_handler = logging.FileHandler(app.config['LOG_FILE'])
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))
logger.handlers = [file_handler, stream_handler]
logger.request_id = 'N/A'

@app.before_request
def before_request():
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4())[:8])
    g.start_time = time.time()
    logging.getLogger().request_id = g.request_id


@app.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        logging.info(f"{request.method} {request.path} - {response.status_code} - {duration:.3f}s")
    response.headers['X-Request-ID'] = g.request_id
    return response


class RateLimiter:
    """Simple in-memory rate limiter."""
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        if key not in self.requests:
            self.requests[key] = []
        
        self.requests[key] = [t for t in self.requests[key] if now - t < window]
        
        if len(self.requests[key]) >= limit:
            return False
        
        self.requests[key].append(now)
        return True

rate_limiter = RateLimiter()


def rate_limit(limit: int = 60, window: int = 60):
    """Rate limiting decorator."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not app.config.get('RATE_LIMIT_ENABLED', True):
                return f(*args, **kwargs)
            
            client_ip = request.remote_addr
            if not rate_limiter.is_allowed(client_ip, limit, window):
                logging.warning(f"Rate limit exceeded for {client_ip}")
                return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def validate_image(file: io.BytesIO) -> tuple[bool, str]:
    """Validate uploaded image file."""
    try:
        img = Image.open(file)
        img.verify()
        file.seek(0)
        
        w, h = img.size
        if w < 1 or h < 1:
            return False, "Invalid image dimensions"
        
        if w * h > 25_000_000:
            return False, "Image too large (max ~5000x5000)"
        
        return True, ""
    except Exception as e:
        return False, f"Invalid image: {str(e)}"


GRADIENT_THEMES = {
    'light': {
        'background': (255, 255, 255),
        'gradient': [(0, 0, 0)]
    },
    'warm': {
        'background': (255, 255, 255),
        'gradient': [
            (255, 255, 255),
            (251, 191, 36),
            (249, 115, 22),
            (220, 38, 38),
            (30, 41, 59),
        ]
    },
    'colorful': {
        'background': (15, 23, 42),
        'gradient': [
            (15, 23, 42),
            (59, 130, 246),
            (139, 92, 246),
            (192, 132, 252),
            (253, 224, 241),
        ]
    },
}


def get_gradient_color(gray_value: int, gradient_colors: list) -> tuple:
    """Get color from gradient based on gray value (0-255)."""
    if len(gradient_colors) < 2:
        return gradient_colors[0] if gradient_colors else (0, 0, 0)
    
    position = gray_value / 255.0
    segment = position * (len(gradient_colors) - 1)
    index = int(segment)
    fraction = segment - index
    
    if index >= len(gradient_colors) - 1:
        return gradient_colors[-1]
    
    c1 = gradient_colors[index]
    c2 = gradient_colors[index + 1]
    
    r = int(c1[0] + (c2[0] - c1[0]) * fraction)
    g = int(c1[1] + (c2[1] - c1[1]) * fraction)
    b = int(c1[2] + (c2[2] - c1[2]) * fraction)
    
    return (r, g, b)


def pixels_to_image(pixels: list, ascii_art: list, theme: str = 'light', 
                    zoom: float = 1.0, orig_w: int = 1, orig_h: int = 1) -> Image.Image:
    """Render ASCII art as a PNG image with proper scaling."""
    if not ascii_art or not pixels:
        return None
    
    theme_data = GRADIENT_THEMES.get(theme, GRADIENT_THEMES['light'])
    gradient_colors = theme_data['gradient']
    bg_color = theme_data['background']
    
    output_width = int(orig_w * zoom)
    output_height = int(orig_h * zoom)
    
    if output_width < 10 or output_height < 10:
        output_width = max(output_width, 10)
        output_height = max(output_height, 10)
    
    img = Image.new('RGB', (output_width, output_height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    font_size = max(8, int(zoom * 10))
    
    try:
        font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'DejaVuSansMono.ttf')
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
    
    ascii_w = max(len(line) for line in ascii_art) if ascii_art else 1
    ascii_h = len(ascii_art) if ascii_art else 1
    
    scale_x = output_width / ascii_w if ascii_w > 0 else 1
    scale_y = output_height / ascii_h if ascii_h > 0 else 1
    
    for y, line in enumerate(ascii_art):
        if y >= len(pixels):
            break
        for x, char in enumerate(line):
            if x >= len(pixels[y]):
                break
            if char == ' ':
                continue
            
            r, g_val, b = pixels[y][x]
            gray = (r * 30 + g_val * 59 + b * 11) // 100
            
            color = get_gradient_color(gray, gradient_colors)
            
            pos_x = int(x * scale_x)
            pos_y = int(y * scale_y)
            
            draw.text((pos_x, pos_y), char, fill=color, font=font)
    
    return img


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'request_id': g.request_id,
        'uptime': 'ok'
    })


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
@rate_limit(limit=30, window=60)
def convert():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, bmp, webp'}), 400
    
    try:
        file_stream = file.stream
        valid, error_msg = validate_image(file_stream)
        if not valid:
            return jsonify({'error': error_msg}), 400
        
        target_width = int(request.form.get('width', app.config['DEFAULT_WIDTH']))
        vertical_scale = int(request.form.get('vertical_scale', app.config['DEFAULT_VERTICAL_SCALE']))
        char_set = request.form.get('char_set', app.config['DEFAULT_CHARSET'])
        reverse = request.form.get('reverse', 'false').lower() == 'true'
        theme = request.form.get('theme', 'light')
        zoom = float(request.form.get('zoom', app.config['DEFAULT_ZOOM']))
        
        if theme not in GRADIENT_THEMES:
            theme = 'light'
        
        if reverse:
            char_set = char_set[::-1]
        
        file.seek(0)
        pil_image = Image.open(file.stream)
        orig_w, orig_h = pil_image.size
        
        pil_image = ascii_converter.validate_image(pil_image, app.config['MAX_IMAGE_DIMENSION'])
        pixels, w, h = ascii_converter.pil_to_pixels(pil_image)
        
        aspect_ratio = h / w
        scaled_h = int(target_width * aspect_ratio * vertical_scale)
        
        resized_pixels, rw, rh = ascii_converter.resize_image_pillow(pil_image, target_width, vertical_scale)
        
        ascii_art = ascii_converter.pixels_to_ascii(resized_pixels, char_set, 1)
        
        ascii_text = '\n'.join(ascii_art)
        
        png_img = pixels_to_image(resized_pixels, ascii_art, theme, zoom, orig_w, orig_h)
        
        img_base64 = None
        if png_img:
            img_io = io.BytesIO()
            png_img.save(img_io, 'PNG', quality=85, optimize=True)
            img_io.seek(0)
            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
        
        del pixels
        del resized_pixels
        del pil_image
        
        return jsonify({
            'ascii_art': ascii_text,
            'dimensions': {'width': rw, 'height': len(ascii_art)},
            'image_available': png_img is not None,
            'image_data': img_base64,
            'orig_dimensions': {'width': orig_w, 'height': orig_h},
            'theme': theme,
            'zoom': zoom
        })
        
    except Exception as e:
        logging.error(f"Conversion error: {str(e)}")
        return jsonify({'error': 'An error occurred processing your image. Please try again.'}), 500


@app.route('/download/txt', methods=['POST'])
@rate_limit(limit=30, window=60)
def download_txt():
    try:
        data = request.get_json()
        ascii_art = data.get('ascii_art', '')
        
        if not ascii_art:
            return jsonify({'error': 'No ASCII art to download'}), 400
        
        return send_file(
            io.BytesIO(ascii_art.encode('utf-8')),
            mimetype='text/plain',
            as_attachment=True,
            download_name='ascii_art.txt'
        )
    except Exception as e:
        logging.error(f"Download TXT error: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500


@app.route('/download/img', methods=['POST'])
@rate_limit(limit=30, window=60)
def download_img():
    try:
        data = request.get_json()
        ascii_art = data.get('ascii_art', '')
        
        if not ascii_art:
            return jsonify({'error': 'No image to download. Generate ASCII art first.'}), 400
        
        theme = data.get('theme', 'light')
        zoom = float(data.get('zoom', 1.0))
        
        file = request.files.get('image')
        pil_image = None
        orig_w, orig_h = 100, 100
        
        if file:
            pil_image = Image.open(file.stream)
            orig_w, orig_h = pil_image.size
            pil_image = ascii_converter.validate_image(pil_image)
            pixels, _, _ = ascii_converter.pil_to_pixels(pil_image)
            
            target_width = 100
            vertical_scale = 2
            resized_pixels, _, _ = ascii_converter.resize_image_pillow(pil_image, target_width, vertical_scale)
            ascii_art_lines = ascii_converter.pixels_to_ascii(resized_pixels, '@%#*+=-:. ', 1)
            
            png_img = pixels_to_image(resized_pixels, ascii_art_lines, theme, zoom, orig_w, orig_h)
            
            del pixels
            del resized_pixels
            del pil_image
        else:
            pixels = [[(128, 128, 128) for _ in range(100)] for _ in range(100)]
            ascii_art_lines = ascii_art.split('\n')[:100]
            png_img = pixels_to_image(pixels, ascii_art_lines, theme, zoom, orig_w, orig_h)
        
        if png_img is None:
            return jsonify({'error': 'Failed to generate image'}), 500
        
        img_io = io.BytesIO()
        png_img.save(img_io, 'PNG', quality=85, optimize=True)
        img_io.seek(0)
        
        return send_file(
            img_io,
            mimetype='image/png',
            as_attachment=True,
            download_name='ascii_art.png'
        )
    except Exception as e:
        logging.error(f"Download IMG error: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    logging.error(f"Server error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
