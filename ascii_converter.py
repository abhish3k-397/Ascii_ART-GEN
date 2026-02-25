#!/usr/bin/env python3
import sys
import argparse
from typing import List, Tuple, Union
from PIL import Image


def validate_image(pil_image: Image.Image, max_dimension: int = 4000) -> Image.Image:
    """Validate and preprocess image."""
    if pil_image.mode not in ('RGB', 'RGBA', 'L'):
        pil_image = pil_image.convert('RGB')
    
    w, h = pil_image.size
    if w > max_dimension or h > max_dimension:
        ratio = min(max_dimension / w, max_dimension / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        pil_image = pil_image.resize((new_w, new_h), Image.ANTIALIAS)
    
    return pil_image


def resize_image_pillow(pil_image: Image.Image, target_width: int, vertical_scale: float = 2.0) -> Tuple[List[List[Tuple[int, int, int]]], int, int]:
    """
    Resize image using Pillow (C-optimized).
    Returns pixel data, width, height.
    """
    w, h = pil_image.size
    aspect_ratio = h / w
    target_height = int(target_width * aspect_ratio * vertical_scale)
    
    resized = pil_image.resize((target_width, target_height), Image.NEAREST)
    
    pixels: List[List[Tuple[int, int, int]]] = []
    for y in range(target_height):
        row: List[Tuple[int, int, int]] = []
        for x in range(target_width):
            pixel = resized.getpixel((x, y))
            if isinstance(pixel, int):
                row.append((pixel, pixel, pixel))
            elif isinstance(pixel, tuple):
                if len(pixel) == 4:
                    row.append((pixel[0], pixel[1], pixel[2]))
                elif len(pixel) == 3:
                    row.append(pixel)
                else:
                    gray = int(pixel[0])
                    row.append((gray, gray, gray))
            else:
                row.append((0, 0, 0))
        pixels.append(row)
    
    return pixels, target_width, target_height


def pixels_to_ascii(pixels: List[List[Tuple[int, int, int]]], ascii_chars: str, vertical_scale: int = 2) -> List[str]:
    """
    Converts a grid of RGB pixels to ASCII characters.
    Uses simple list comprehension for performance.
    """
    ascii_output: List[str] = []
    char_count = len(ascii_chars)
    max_idx = char_count - 1
    
    for y in range(0, len(pixels), vertical_scale):
        row = pixels[y]
        ascii_row = ''
        for r, g, b in row:
            gray = (r * 30 + g * 59 + b * 11) // 100
            idx = (gray * max_idx) // 255
            ascii_row += ascii_chars[idx]
        ascii_output.append(ascii_row)
    
    return ascii_output


def pil_to_pixels(pil_image: Image.Image) -> Tuple[List[List[Tuple[int, int, int]]], int, int]:
    """Convert PIL image to pixel data."""
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')
    
    w, h = pil_image.size
    pixels: List[List[Tuple[int, int, int]]] = []
    
    for y in range(h):
        row: List[Tuple[int, int, int]] = []
        for x in range(w):
            r, g, b = pil_image.getpixel((x, y))
            row.append((r, g, b))
        pixels.append(row)
    
    return pixels, w, h


def parse_bmp(file_path: str):
    """
    Parses a BMP file and returns its pixel data, width, height, and bits per pixel.
    Supports 24-bit and 32-bit BMPs.
    """
    with open(file_path, "rb") as f:
        bmp = bytearray(f.read())

    if bmp[0:2] != b'BM':
        raise ValueError("Not a valid BMP file")

    data_offset = int.from_bytes(bmp[10:14], "little")
    width = int.from_bytes(bmp[18:22], "little", signed=True)
    height = int.from_bytes(bmp[22:26], "little", signed=True)
    bpp = int.from_bytes(bmp[28:30], "little")

    if bpp not in (24, 32):
        raise ValueError(f"Unsupported bits per pixel: {bpp}. Only 24-bit and 32-bit are supported.")

    abs_w = abs(width)
    abs_h = abs(height)
    bytes_per_pixel = bpp // 8
    
    row_size = (abs_w * bytes_per_pixel + 3) & ~3
    
    pixels: List[List[Tuple[int, int, int]]] = []
    for y in range(abs_h):
        row_data: List[Tuple[int, int, int]] = []
        if height > 0:
            row_start = data_offset + (abs_h - 1 - y) * row_size
        else:
            row_start = data_offset + y * row_size

        for x in range(abs_w):
            pixel_start = row_start + x * bytes_per_pixel
            b = bmp[pixel_start]
            g = bmp[pixel_start + 1]
            r = bmp[pixel_start + 2]
            row_data.append((r, g, b))
        pixels.append(row_data)

    return pixels, abs_w, abs_h


def main():
    parser = argparse.ArgumentParser(description="Convert BMP images to ASCII art.")
    parser.add_argument("input", help="Path to the input BMP file")
    parser.add_argument("-o", "--output", help="Path to save the output text file")
    parser.add_argument("-w", "--width", type=int, default=100, help="Target width of the ASCII art (default: 100)")
    parser.add_argument("-v", "--vertical-scale", type=int, default=2, help="Vertical scale factor (default: 2)")
    parser.add_argument("-s", "--set", default="@%#*+=-:. ", help="ASCII character set")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse the ASCII character set intensities")

    args = parser.parse_args()

    ascii_set = args.set[::-1] if args.reverse else args.set

    try:
        pixels, w, h = parse_bmp(args.input)
        print(f"Loaded {w}x{h} BMP image.")
        
        pil_image = Image.new('RGB', (w, h))
        for y, row in enumerate(pixels):
            for x, pixel in enumerate(row):
                pil_image.putpixel((x, y), pixel)
        
        resized_pixels, rw, rh = resize_image_pillow(pil_image, args.width, args.vertical_scale)
        print(f"Resized to target width {rw} (height adjusted to {rh}).")
        
        ascii_art = pixels_to_ascii(resized_pixels, ascii_set, 1)
        
        for line in ascii_art:
            print(line)
            
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                for line in ascii_art:
                    f.write(line + "\n")
            print(f"\nASCII art saved to {args.output}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
