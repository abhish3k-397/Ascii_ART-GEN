#!/usr/bin/env python3
import sys
import argparse

def parse_bmp(file_path):
    """
    Parses a BMP file and returns its pixel data, width, height, and bits per pixel.
    Supports 24-bit and 32-bit BMPs.
    """
    with open(file_path, "rb") as f:
        bmp = bytearray(f.read())

    # Basic check for BM signature
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
    
    # BMP rows are padded to 4-byte boundaries
    row_size = (abs_w * bytes_per_pixel + 3) & ~3
    
    pixels = []
    # BMP is usually stored bottom-to-top. If height is positive, it's bottom-to-top.
    # If height is negative, it's top-to-bottom.
    for y in range(abs_h):
        row_data = []
        # Calculate row start based on storage order
        if height > 0:
            row_start = data_offset + (abs_h - 1 - y) * row_size
        else:
            row_start = data_offset + y * row_size

        for x in range(abs_w):
            pixel_start = row_start + x * bytes_per_pixel
            b = bmp[pixel_start]
            g = bmp[pixel_start + 1]
            r = bmp[pixel_start + 2]
            # Ignore alpha channel for 32-bit if it exists
            row_data.append((r, g, b))
        pixels.append(row_data)

    return pixels, abs_w, abs_h

def resize_image(pixels, original_w, original_h, new_width):
    """
    Resizes the pixel grid using nearest-neighbor interpolation.
    Maintains aspect ratio.
    """
    scale = new_width / original_w
    new_height = int(original_h * scale)
    
    resized_pixels = []
    for y in range(new_height):
        src_y = int(y / scale)
        # Ensure index is within bounds
        src_y = min(src_y, original_h - 1)
        row = []
        for x in range(new_width):
            src_x = int(x / scale)
            src_x = min(src_x, original_w - 1)
            row.append(pixels[src_y][src_x])
        resized_pixels.append(row)
    
    return resized_pixels, new_width, new_height

def pixels_to_ascii(pixels, ascii_chars, vertical_scale=2):
    """
    Converts a grid of RGB pixels to ASCII characters.
    """
    ascii_output = []
    for y, row in enumerate(pixels):
        # Apply vertical scale (skip rows to reduce height)
        if y % vertical_scale != 0:
            continue
            
        ascii_row = ""
        for r, g, b in row:
            # Luminance formula: 0.299*R + 0.587*G + 0.114*B
            # We use an approximation (30R + 59G + 11B) // 100 for integer math
            gray = (r * 30 + g * 59 + b * 11) // 100
            
            # Map 0-255 to 0-(len(ASCII)-1)
            idx = gray * (len(ascii_chars) - 1) // 255
            ascii_row += ascii_chars[idx]
        ascii_output.append(ascii_row)
    
    return ascii_output

def main():
    parser = argparse.ArgumentParser(description="Convert BMP images to ASCII art.")
    parser.add_argument("input", help="Path to the input BMP file")
    parser.add_argument("-o", "--output", help="Path to save the output text file")
    parser.add_argument("-w", "--width", type=int, default=100, help="Target width of the ASCII art (default: 100)")
    parser.add_argument("-v", "--vertical-scale", type=int, default=2, help="Vertical scale factor to compensate for font aspect ratio (default: 2)")
    parser.add_argument("-s", "--set", default="@%#*+=-:. ", help="ASCII character set to use (from dark to light)")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse the ASCII character set intensities")

    args = parser.parse_args()

    ascii_set = args.set
    if args.reverse:
        ascii_set = ascii_set[::-1]

    try:
        pixels, w, h = parse_bmp(args.input)
        print(f"Loaded {w}x{h} BMP image.")
        
        resized_pixels, rw, rh = resize_image(pixels, w, h, args.width)
        print(f"Resized to target width {rw} (height adjusted to {rh}).")
        
        ascii_art = pixels_to_ascii(resized_pixels, ascii_set, args.vertical_scale)
        
        # Output to terminal
        for line in ascii_art:
            print(line)
            
        # Output to file if requested
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
