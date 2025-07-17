FROM python:3.12.2-slim-bullseye

# Node.js dla Tailwind
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# Node.js deps dla theme
COPY theme/static_src/package*.json ./theme/static_src/
RUN cd theme/static_src && npm install

# Kopiuj wszystko
COPY . .

# Build CSS dla dev
RUN cd theme/static_src && npm run dev &

# Dev server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
EXPOSE 8000