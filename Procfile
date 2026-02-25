# For Termux/lightweight deployment - use Flask built-in server
web: python -c "from app import app; app.run(host='0.0.0.0', port=\$PORT, threaded=True)"

# For production with gunicorn (if you have more resources)
# web: gunicorn app:app -w 1 --threads 4 -t 60
