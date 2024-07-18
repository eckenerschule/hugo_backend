# ./uwsgi.py
from app.main import app as application

if __name__ == '__main__':
    application.run(debug=True, port=5000, host='0.0.0.0')