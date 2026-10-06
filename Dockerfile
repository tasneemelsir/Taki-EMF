# Taki in one container: the Python server and the web interface.
#
#   docker build -t taki .
#   docker run -p 8000:8000 -v taki-data:/data taki                    data in a local volume
#   docker run -p 8000:8000 -e DATABASE_URL=postgresql://... taki      data in an online database
#
# Hosting platforms (Render, Railway, Cloud Run ...) build this file as it is and
# pass the port to listen on in $PORT, which Taki reads. Give them DATABASE_URL
# as well: their own disks are wiped on every deploy.
#
# The interface is already built in server/static. After changing anything under
# web/, rebuild it first:  cd web && npm install && npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg \
    TAKI_HOST=0.0.0.0 TAKI_DATA_DIR=/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY run.py ./
COPY engine/ engine/
COPY server/ server/
# What the site hands out as the desktop version ("Taki as an app" in the account menu).
# Leave these three COPY lines out and the site simply does not offer the download.
COPY desktop.py requirements-desktop.txt requirements-desktop.lock install-desktop.bat start-desktop.sh ./
COPY tools/desktop_setup.py tools/
COPY tools/wheels/ tools/wheels/
RUN useradd --create-home taki && mkdir -p /data && chown taki /data
USER taki
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health' % (os.environ.get('TAKI_PORT') or os.environ.get('PORT') or '8000'))" || exit 1
CMD ["python", "run.py", "--no-browser"]
