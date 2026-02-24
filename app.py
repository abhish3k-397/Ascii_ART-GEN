#!/usr/bin/env python3
import os
import io
import tempfile
import base64
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import ascii_converter

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

last_generated_image = None

GRADIENT_THEMES = {
    'light': {
        'background': (255, 255, 255),
        'gradient': [
            (0, 0, 0),
        ]
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

def pil_to_pixels(pil_image):
    """Convert PIL image to pixel data compatible with ascii_converter."""
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')
    
    pixels = []
    for y in range(pil_image.height):
        row = []
        for x in range(pil_image.width):
            r, g, b = pil_image.getpixel((x, y))
            row.append((r, g, b))
        pixels.append(row)
    return pixels, pil_image.width, pil_image.height

def get_gradient_color(gray_value, gradient_colors):
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

def pixels_to_image(pixels, ascii_art, theme='light', zoom=1.0, orig_w=1, orig_h=1):
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
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
    except:
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
            
            r, g, b = pixels[y][x]
            gray = (r * 30 + g * 59 + b * 11) // 100
            
            color = get_gradient_color(gray, gradient_colors)
            
            pos_x = int(x * scale_x)
            pos_y = int(y * scale_y)
            
            draw.text((pos_x, pos_y), char, fill=color, font=font)
    
    return img

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    try:
        target_width = int(request.form.get('width', 100))
        vertical_scale = int(request.form.get('vertical_scale', 2))
        char_set = request.form.get('char_set', '@%#*+=-:. ')
        reverse = request.form.get('reverse', 'false').lower() == 'true'
        theme = request.form.get('theme', 'light')
        zoom = float(request.form.get('zoom', 1.0))
        
        if theme not in GRADIENT_THEMES:
            theme = 'light'
        
        if reverse:
            char_set = char_set[::-1]
        
        pil_image = Image.open(file.stream)
        orig_w, orig_h = pil_image.size
        
        pixels, w, h = pil_to_pixels(pil_image)
        
        aspect_ratio = h / w
        scaled_w = target_width
        scaled_h = int(target_width * aspect_ratio * vertical_scale)
        
        resized_pixels, rw, rh = ascii_converter.resize_image(pixels, w, h, target_width)
        
        ascii_art = ascii_converter.pixels_to_ascii(resized_pixels, char_set, 1)
        
        ascii_text = '\n'.join(ascii_art)
        
        png_img = pixels_to_image(resized_pixels, ascii_art, theme, zoom, orig_w, orig_h)
        
        global last_generated_image
        last_generated_image = None
        
        img_base64 = None
        if png_img:
            img_io = io.BytesIO()
            png_img.save(img_io, 'PNG', quality=95)
            img_io.seek(0)
            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            img_io.seek(0)
            last_generated_image = img_io.getvalue()
        
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
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/download/txt', methods=['POST'])
def download_txt():
    data = request.get_json()
    ascii_art = data.get('ascii_art', '')
    
    return send_file(
        io.BytesIO(ascii_art.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name='ascii_art.txt'
    )

@app.route('/download/img', methods=['POST'])
def download_img():
    global last_generated_image
    
    if last_generated_image is None:
        return jsonify({'error': 'No image to download. Generate ASCII art first.'}), 400
    
    img_io = io.BytesIO(last_generated_image)
    
    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=True,
        download_name='ascii_art.png'
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
