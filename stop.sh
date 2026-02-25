#!/bin/bash
# Stop ASCII Art Generator

pkill -f "python.*app.py" && echo "Server stopped" || echo "Server was not running"
